"""Show the terminal GUI in a browser through Xpra until interrupted; optionally publish it with a Cloudflare tunnel."""

from __future__ import annotations

import os
import platform
import re
import secrets
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import config, wineenv
from .config import IS_LINUX, IS_MAC, IS_WIN
from .discovery import prefix_of
from .errors import SetupError
from .installer import _distro, _get, _sudo, ask, ensure_wine, ensure_xvfb, install_packages, package_manager
from .server import is_loopback

__all__ = ["serve_display", "setup_display", "display_status", "find_xpra", "find_cloudflared"]

_XPRA_PKGS = {
    "apt-get": ["xpra", "xpra-html5"],
    "dnf": ["xpra", "xpra-html5"],
    "pacman": ["xpra"],
    "zypper": ["xpra"],
}
_XPRA_WIN_FILES = ("Xpra-x86_64_Setup.exe", "Xpra_Setup.exe")
_XPRA_WIN_BASE = "https://xpra.org/stable/windows/"
_XPRA_REPO = "https://raw.githubusercontent.com/Xpra-org/xpra/master/packaging/repos/{}/{}"
_XPRA_KEY = "https://xpra.org/xpra.asc"
_XPRA_LIST = Path("/etc/apt/sources.list.d/xpra.sources")
_XPRA_KEYFILE = Path("/usr/share/keyrings/xpra.asc")
_HTML5_DIRS = ("/usr/share/xpra/www", "/usr/local/share/xpra/www")


def find_xpra() -> str | None:
    """Path of the Xpra executable, or None when it is not installed."""
    p = shutil.which("xpra") or shutil.which("Xpra_cmd")
    if p:
        return p
    if IS_WIN:
        for var in ("ProgramFiles", "ProgramFiles(x86)"):
            if os.environ.get(var):
                c = Path(os.environ[var]) / "Xpra" / "Xpra_cmd.exe"
                if c.is_file():
                    return str(c)
    elif IS_MAC:
        for c in sorted(Path("/Applications/Xpra.app/Contents").glob("*/[Xx]pra")):
            if c.is_file():
                return str(c)
    return None


def _html5_dir() -> str | None:
    return next((d for d in _HTML5_DIRS if Path(d).is_dir()), None)


def find_cloudflared() -> str | None:
    """Path of cloudflared (on PATH or downloaded by mtx), or None."""
    p = shutil.which("cloudflared")
    if p:
        return p
    c = config.home() / "bin" / ("cloudflared.exe" if IS_WIN else "cloudflared")
    return str(c) if c.is_file() else None


def display_status(tunnel: bool = False) -> dict[str, str | None]:
    """What the display needs on this system, each mapped to its location or None when missing.

    Windows needs only Xpra; Linux adds the Xpra HTML5 client, Xvfb and Wine; macOS adds Wine. cloudflared is listed
    when tunnel is true.
    """
    st: dict[str, str | None] = {"xpra": find_xpra()}
    if IS_LINUX:
        st["xpra_html5"] = _html5_dir()
        st["xvfb"] = shutil.which("Xvfb")
    if not IS_WIN:
        st["wine"] = wineenv.wine_bin()
    if tunnel:
        st["cloudflared"] = find_cloudflared()
    return st


def _install_xpra_exe(yes: bool) -> None:
    urls = [u for u in [os.environ.get("MTX_URL_XPRA_WINDOWS")] if u] + [_XPRA_WIN_BASE + n for n in _XPRA_WIN_FILES]
    folder = config.home() / "downloads"
    folder.mkdir(parents=True, exist_ok=True)
    errors = []
    for url in urls:
        exe = folder / url.rsplit("/", 1)[-1]
        try:
            _get(url, exe, True)
        except (urllib.error.URLError, OSError, ValueError) as e:
            errors.append(f"{url}: {e}")
            exe.unlink(missing_ok=True)
            continue
        if ask("The Xpra installer will ask for administrator permission. Start it now?", yes):
            subprocess.call([str(exe), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
        return
    raise SetupError("could not download Xpra; install it from https://xpra.org/ and run again:\n  " + "\n  ".join(errors))


def _codename() -> str | None:
    try:
        d = dict(ln.split("=", 1) for ln in Path("/etc/os-release").read_text().splitlines() if "=" in ln)
    except OSError:
        return None
    return (d.get("UBUNTU_CODENAME") or d.get("VERSION_CODENAME") or "").strip('"') or None


def _system_python_minor() -> int:
    try:
        out = subprocess.run(["/usr/bin/python3", "-c", "import sys;print(sys.version_info.minor)"], capture_output=True, text=True, timeout=20).stdout
        return int(out.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return sys.version_info.minor


def _xpra_suites(name: str) -> list[str]:
    """Repository names to try, the system's own first, then the releases whose packages fit this system's Python best."""
    ubuntu = "ubuntu" in _distro()
    py = _system_python_minor()
    if py >= 14:
        rest = ["resolute", "forky", "sid", "trixie", "noble"] if ubuntu else ["forky", "sid", "trixie"]
    elif py == 13:
        rest = ["trixie", "resolute", "noble", "jammy"] if ubuntu else ["trixie", "forky", "bookworm"]
    else:
        rest = ["noble", "jammy", "resolute", "trixie"] if ubuntu else ["bookworm", "trixie"]
    return [name] + [n for n in rest if n != name]


def _apt_can_install(pkgs: list[str]) -> bool:
    return subprocess.call(["apt-get", "-s", "install", *pkgs], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def _add_xpra_repo(yes: bool) -> bool:
    """Debian and Ubuntu ship an outdated or missing Xpra: add the official xpra.org repository. True when a working one is in place.

    A repository counts only when its packages can be installed on this system. When xpra.org has no repository for this
    release, or its packages do not fit (for example they need an older Python), nearby releases are tried in turn.
    """
    name = _codename()
    if not name or not ({"debian", "ubuntu"} & _distro()):
        return False
    pkgs = _XPRA_PKGS["apt-get"]
    if _XPRA_LIST.is_file():
        if _apt_can_install(pkgs):
            return True
        if not ask("The Xpra repository already added does not fit this system. Replace it?", yes):
            return False
        _sudo(["rm", "-f", str(_XPRA_LIST)], yes)
    tmp = Path(tempfile.mkdtemp(prefix="mtx-xpra-"))
    try:
        try:
            _get(_XPRA_KEY, tmp / "xpra.asc", False)
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"could not download the Xpra signing key: {e}", file=sys.stderr)
            return False
        if not ask("Add the official Xpra repository (xpra.org)? Releases close to this one are tried if it has none that fits.", yes):
            return False
        if _sudo(["install", "-m", "644", str(tmp / "xpra.asc"), str(_XPRA_KEYFILE)], yes) != 0:
            return False
        for suite in _xpra_suites(name):
            for f in ("xpra.sources", "xpra-lts.sources", "xpra-beta.sources"):
                src = tmp / f
                try:
                    _get(_XPRA_REPO.format(suite, f), src, False)
                except (urllib.error.URLError, OSError, ValueError):
                    continue
                if _sudo(["install", "-m", "644", str(src), str(_XPRA_LIST)], yes) != 0:
                    return False
                if _sudo(["apt-get", "update"], yes) == 0 and _apt_can_install(pkgs):
                    if suite != name:
                        print(f"using the xpra.org repository for {suite}")
                    return True
                _sudo(["rm", "-f", str(_XPRA_LIST)], yes)
        print(f"no xpra.org repository fits {name}; see https://xpra-org.github.io/xpra/Download/", file=sys.stderr)
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _install_xpra(yes: bool) -> None:
    if IS_WIN:
        if shutil.which("winget"):
            cmd = ["winget", "install", "--id", "xpra-org.xpra", "--exact", "--silent"]
            if subprocess.call([*cmd, "--accept-package-agreements", "--accept-source-agreements"]) == 0:
                return
        _install_xpra_exe(yes)
    elif IS_MAC:
        if not shutil.which("brew"):
            raise SetupError("install Homebrew, or the Xpra package from https://xpra.org/, and run again")
        if subprocess.call(["brew", "install", "--cask", "xpra"]) != 0:
            raise SetupError("could not install Xpra with Homebrew; install Xpra.dmg from https://xpra.org/ and run again")
    else:
        mgr = package_manager()
        if not mgr:
            raise SetupError("no supported package manager found; install Xpra from https://xpra.org/ and run again")
        if mgr == "apt-get" and not _add_xpra_repo(yes):
            print("Xpra will be installed from the distribution's own packages if it has any", file=sys.stderr)
        if install_packages(_XPRA_PKGS[mgr], yes) != 0:
            raise SetupError("could not install Xpra for this system; see https://xpra-org.github.io/xpra/Download/ for supported releases and run again")


def _ensure_xpra(yes: bool) -> str:
    x = find_xpra()
    if x and (not IS_LINUX or _html5_dir()):
        return x
    if not ask("Xpra is missing. Install it? (administrator permission may be asked)" if not x else "The Xpra HTML5 client is missing. Install it?", yes):
        raise SetupError("Xpra is required; run: mtx display setup")
    _install_xpra(yes)
    x = find_xpra()
    if not x:
        raise SetupError("Xpra is required; install it (https://xpra.org/) and run again")
    if IS_LINUX and not _html5_dir():
        print("warning: the Xpra HTML5 client (xpra-html5) was not found; the browser page may not load", file=sys.stderr)
    return x


def _ensure_cloudflared(yes: bool) -> str:
    c = find_cloudflared()
    if c:
        return c
    if IS_MAC:
        if not shutil.which("brew"):
            raise SetupError("install cloudflared (brew install cloudflared) and run again")
        if not ask("cloudflared is missing. Install it with Homebrew?", yes):
            raise SetupError("cloudflared is required for --tunnel")
        subprocess.call(["brew", "install", "cloudflared"])
        c = find_cloudflared()
        if not c:
            raise SetupError("cloudflared did not install; run: brew install cloudflared")
        return c
    m = platform.machine().lower()
    arch = "arm64" if m in ("arm64", "aarch64") else "amd64"
    name = "cloudflared-windows-amd64.exe" if IS_WIN else f"cloudflared-linux-{arch}"
    if not ask("cloudflared is missing. Download it from GitHub for a temporary public link?", yes):
        raise SetupError("cloudflared is required for --tunnel")
    dest = config.home() / "bin" / ("cloudflared.exe" if IS_WIN else "cloudflared")
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(f"https://github.com/cloudflare/cloudflared/releases/latest/download/{name}", dest)
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR)
    return str(dest)


def setup_display(yes: bool = False, tunnel: bool = False) -> dict[str, str | None]:
    """Install everything needed to show the terminal in a browser and return the resulting display_status.

    Xpra (with its HTML5 client) on every system, plus Wine and Xvfb on Linux and Wine on macOS. cloudflared is added
    when tunnel is true. Each missing piece is asked about first and administrator permission is requested only when
    the package manager needs it; yes answers every question.
    """
    if not IS_WIN:
        ensure_wine(yes)
    if IS_LINUX:
        ensure_xvfb(yes)
    _ensure_xpra(yes)
    if tunnel:
        _ensure_cloudflared(yes)
    return display_status(tunnel)


def _ensure_ready(yes: bool, tunnel: bool) -> str:
    missing = [k for k, v in display_status(tunnel).items() if not v]
    if missing:
        if not ask(f"Missing for the display: {', '.join(missing)}. Install now?", yes, False):
            raise SetupError("the display needs " + ", ".join(missing) + "; run: mtx display setup")
        setup_display(True, tunnel)
    return _ensure_xpra(yes)


def _tunnel(cf: str, port: int) -> subprocess.Popen:
    proc = subprocess.Popen(
        [cf, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    def pump() -> None:
        for line in proc.stdout:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m:
                print(f"public link: {m.group(0)}")

    threading.Thread(target=pump, daemon=True).start()
    return proc


def _terminal_running(terminal: str) -> bool:
    name = Path(terminal).name.lower()
    me = str(os.getpid())
    try:
        for c in Path("/proc").glob("[0-9]*/cmdline"):
            if c.parent.name == me:
                continue
            for arg in c.read_bytes().decode("utf-8", "ignore").lower().split("\0"):
                if re.split(r"[\\/]", arg)[-1] == name:
                    return True
    except OSError:
        pass
    return False


def _stop_terminal(terminal: str) -> None:
    """Close the terminal, and on Wine everything else running in its prefix, waiting a few seconds for it to go."""
    if IS_WIN:
        subprocess.call(["taskkill", "/F", "/IM", Path(terminal).name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        pre = prefix_of(terminal)
        if pre:
            wineenv.kill_server(pre)
        else:
            subprocess.call(["pkill", "-fi", Path(terminal).name])
    for _ in range(20):
        if IS_WIN or not _terminal_running(terminal):
            return
        time.sleep(0.5)


def _port_free(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET) as s:
            s.bind((host, port))
        return True
    except OSError:
        return False


def pick_port(host: str, port: int | None = None) -> int:
    """The port to serve on: the requested one, which must be free, or else the first free port from 14500.

    Raises:
        SetupError: The requested port is in use, or no port from 14500 to 14599 is free.
    """
    if port:
        if not _port_free(host, port):
            raise SetupError(f"port {port} is already in use; choose another with --port")
        return port
    for p in range(14500, 14600):
        if _port_free(host, p):
            return p
    raise SetupError("no free port from 14500 to 14599; choose one with --port")


def serve_display(
    terminal: str,
    host: str = "127.0.0.1",
    port: int | None = None,
    password: str | None = None,
    tunnel: bool = False,
    yes: bool = False,
    force: bool = False,
) -> int:
    """Run the terminal and publish its window in a browser. Stops, and closes the terminal, on Ctrl+C.

    Missing dependencies are offered for installation first (see setup_display). A password is generated and printed
    when the page is public (tunnel, or a host that is not loopback) and none is given. With force, a running terminal
    (and anything else in its Wine prefix) is closed first so the display starts from a clean state.
    """
    xpra = _ensure_ready(yes, tunnel)
    port = pick_port(host, port)
    if force:
        _stop_terminal(terminal)
    public = tunnel or not is_loopback(host)
    if public and not password:
        password = secrets.token_urlsafe(9)
        print(f"password: {password}")
    env = os.environ.copy()
    if password:
        env["XPRA_PASSWORD"] = password
    common = [f"--bind-tcp={host}:{port}", "--html=on", "--mdns=no", "--notifications=no", "--printing=no", "--webcam=no", "--pulseaudio=no", "--input-method=none"]
    if password:
        common.append("--tcp-auth=env")
    child: subprocess.Popen | None = None
    if IS_WIN:
        if is_loopback(host):
            print("note: on Windows the whole desktop is shared, so open this page from another device; on this machine it mirrors itself", file=sys.stderr)
        child = subprocess.Popen([terminal], cwd=str(Path(terminal).parent))
        cmd = [xpra, "shadow", *common]
    else:
        wine = wineenv.wine_bin()
        if not wine:
            raise SetupError("wine was not found; run: mtx setup")
        pre = prefix_of(terminal)
        if pre:
            env["WINEPREFIX"] = str(pre)
        env["WINEDEBUG"] = wineenv.winedebug()
        if _terminal_running(terminal):
            raise SetupError(f"{Path(terminal).name} is already running (for example from `mtx serve`); stop it first or use --force")
        log = config.home() / "logs" / "terminal.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        disp = f":{700 + secrets.randbelow(200)}"
        child_cmd = f"exec {shlex.join([wine, terminal])} >> {shlex.quote(str(log))} 2>&1"
        cmd = [xpra, "start", disp, *common, "--daemon=no", "--exit-with-children=yes", "--start-child=" + shlex.join(["sh", "-c", child_cmd])]
    cf = _tunnel(_ensure_cloudflared(yes), port) if tunnel else None
    started = time.monotonic()
    proc = subprocess.Popen(cmd, env=env)
    print(f"terminal display: http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}/   (Ctrl+C to stop)")
    try:
        while proc.poll() is None:
            time.sleep(0.5)
        if not IS_WIN and time.monotonic() - started < 30:
            print(f"the terminal exited right away; its output is in {config.home() / 'logs' / 'terminal.log'} (run with --winedebug fixme for more)", file=sys.stderr)
        return proc.returncode or 0
    except KeyboardInterrupt:
        return 0
    finally:
        for p in (cf, proc, child):
            if p is not None and p.poll() is None:
                p.terminate()
        for p in (cf, proc, child):
            if p is not None:
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    p.kill()
