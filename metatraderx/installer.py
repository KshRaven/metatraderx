"""Download and install MetaTrader 5/4 and the Wine pieces the Linux and macOS backend needs."""

from __future__ import annotations

import os
import platform
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from . import config, wineenv
from .config import IS_LINUX, IS_MAC, IS_WIN
from .errors import SetupError

__all__ = [
    "download", "install", "setup_wine_python", "ensure_wine", "ensure_xvfb", "install_packages", "package_manager",
    "os_key", "candidate_urls", "ask",
]  # fmt: skip

UA = "Mozilla/5.0 (compatible; MetaTraderX)"
HOSTS = ("https://download.mql5.com", "https://download.terminal.free")
_BASE = "/cdn/web/metaquotes.software.corp"
PATHS = {
    (5, "windows"): [f"{_BASE}/mt5/mt5setup.exe"],
    (5, "linux"): [f"{_BASE}/mt5/mt5linux.sh", f"{_BASE}/mt5/mt5ubuntu.sh", "/cdn/web/metaquotes.ltd/mt5/mt5ubuntu.sh"],
    (5, "macos"): [f"{_BASE}/mt5/MetaTrader5.dmg"],
    (4, "windows"): [f"{_BASE}/mt4/mt4setup.exe"],
    (4, "linux"): [f"{_BASE}/mt4/mt4linux.sh", f"{_BASE}/mt4/mt4ubuntu.sh", "/cdn/web/metaquotes.ltd/mt4/mt4ubuntu.sh"],
    (4, "macos"): [f"{_BASE}/mt4/MetaTrader4.dmg"],
}
PYTHON_URL = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
PYTHON_DIR = "C:\\Python312"
_PKG = {
    "apt-get": (["apt-get", "install", "-y"], ["wine", "xvfb"]),
    "dnf": (["dnf", "install", "-y"], ["wine", "xorg-x11-server-Xvfb"]),
    "pacman": (["pacman", "-S", "--noconfirm"], ["wine", "xorg-server-xvfb"]),
    "zypper": (["zypper", "install", "-y"], ["wine", "xorg-x11-server-Xvfb"]),
}


def os_key() -> str:
    """"windows", "macos" or "linux" for this system."""
    return "windows" if IS_WIN else "macos" if IS_MAC else "linux"


def ask(question: str, yes: bool = False, default: bool = True) -> bool:
    """Ask a yes/no question. yes answers True without asking; with no terminal attached the default is returned."""
    if yes:
        return True
    if not sys.stdin.isatty():
        return default
    r = input(f"{question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    return default if not r else r in ("y", "yes")


def candidate_urls(version: int, key: str | None = None) -> list[str]:
    """Installer download addresses to try, in order; MTX_URL_MT<version>_<OS> comes first when set."""
    key = key or os_key()
    env = os.environ.get(f"MTX_URL_MT{version}_{key.upper()}")
    urls = [env] if env else []
    for p in PATHS[(version, key)]:
        urls += [h + p for h in HOSTS]
    return urls


def _curl(url: str, dest: Path, show: bool) -> None:
    exe = shutil.which("curl.exe" if IS_WIN else "curl")
    if not exe:
        raise ValueError("curl is not available")
    part = dest.with_name(dest.name + ".part")
    cmd = [exe, "-fL", "--retry", "2", "--connect-timeout", "30", "-A", UA, "-o", str(part), url]
    if not show:
        cmd.insert(1, "-s")
    if subprocess.call(cmd) != 0 or not part.exists() or part.stat().st_size == 0:
        part.unlink(missing_ok=True)
        raise ValueError("curl download failed")
    with open(part, "rb") as f:
        head = f.read(64).lstrip().lower()
    if head.startswith((b"<!doctype", b"<html")):
        part.unlink(missing_ok=True)
        raise ValueError("unexpected HTML response")
    part.replace(dest)


def _get(url: str, dest: Path, show: bool) -> None:
    try:
        _fetch(url, dest, show)
    except urllib.error.URLError as e:
        if isinstance(e.reason, (ssl.SSLError, TimeoutError)):
            _curl(url, dest, show)
        else:
            raise
    except TimeoutError:
        _curl(url, dest, show)


def _fetch(url: str, dest: Path, show: bool) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        if "text/html" in r.headers.get("Content-Type", ""):
            raise ValueError("unexpected HTML response")
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        part = dest.with_name(dest.name + ".part")
        with open(part, "wb") as f:
            while True:
                chunk = r.read(1 << 18)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if show and total:
                    sys.stderr.write(f"\r  {dest.name}  {done * 100 // total:3d}%  {done >> 20} MB")
                    sys.stderr.flush()
    if total and done != total:
        part.unlink(missing_ok=True)
        raise ValueError("incomplete download")
    part.replace(dest)
    if show:
        sys.stderr.write("\n")


def download(version: int = 5, key: str | None = None, dest: str | Path | None = None, show: bool = True) -> Path:
    """Fetch the official installer for a platform ('windows', 'linux', 'macos'; default: this system)."""
    key = key or os_key()
    folder = Path(dest) if dest else config.home() / "downloads"
    folder.mkdir(parents=True, exist_ok=True)
    errors = []
    for url in candidate_urls(version, key):
        out = folder / url.rsplit("/", 1)[-1]
        try:
            _get(url, out, show)
            return out
        except (urllib.error.URLError, OSError, ValueError) as e:
            errors.append(f"{url}: {e}")
            out.unlink(missing_ok=True)
    raise SetupError("could not download the installer:\n  " + "\n  ".join(errors))


def _distro() -> set[str]:
    try:
        d = dict(ln.split("=", 1) for ln in Path("/etc/os-release").read_text().splitlines() if "=" in ln)
    except OSError:
        return set()
    return {d.get("ID", "").strip('"'), *d.get("ID_LIKE", "").strip('"').split()}


def _sudo(cmd: list[str], yes: bool) -> int:
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        if not shutil.which("sudo"):
            raise SetupError("administrator rights are needed; run as root or install sudo")
        print("Administrator permission is needed for: " + " ".join(cmd))
        cmd = ["sudo", *cmd]
    return subprocess.call(cmd)


def package_manager() -> str | None:
    """The first supported Linux package manager on PATH: apt-get, dnf, pacman or zypper."""
    return next((m for m in _PKG if shutil.which(m)), None)


def install_packages(pkgs: list[str], yes: bool = False) -> int:
    """Install packages with the system package manager (asking for administrator rights when needed); returns its exit code."""
    mgr = package_manager()
    if not mgr:
        raise SetupError("no supported package manager found (apt-get, dnf, pacman, zypper); install manually: " + ", ".join(pkgs))
    if mgr == "apt-get":
        _sudo(["apt-get", "update"], yes)
    return _sudo([*_PKG[mgr][0], *pkgs], yes)


def ensure_wine(yes: bool = False) -> str:
    """Return the wine binary, installing wine (and Xvfb) through the system package manager when missing."""
    w = wineenv.wine_bin()
    if w:
        return w
    if IS_WIN:
        raise SetupError("wine is not used on Windows")
    if IS_MAC:
        if not shutil.which("brew"):
            raise SetupError("install Homebrew or the official MetaTrader 5 app, then retry")
        if not ask("Wine is missing. Install it with Homebrew?", yes):
            raise SetupError("wine is required")
        subprocess.call(["brew", "install", "--cask", "wine-stable"])
    else:
        mgr = package_manager()
        if not mgr:
            raise SetupError("wine is missing and no supported package manager was found; install wine manually")
        if not ask(f"Wine is missing. Install it with {mgr}?", yes):
            raise SetupError("wine is required")
        if install_packages(_PKG[mgr][1], yes) != 0:
            raise SetupError("package installation failed")
    w = wineenv.wine_bin()
    if not w:
        raise SetupError("wine was installed but is not on PATH; set MTX_WINE")
    return w


def ensure_xvfb(yes: bool = False) -> str | None:
    """Linux: return the Xvfb binary (a virtual screen for headless hosts), installing it when missing. None elsewhere."""
    if IS_WIN or IS_MAC:
        return None
    x = shutil.which("Xvfb")
    if x:
        return x
    mgr = package_manager()
    if not mgr:
        raise SetupError("Xvfb is missing and no supported package manager was found; install it manually")
    if not ask(f"Xvfb is missing. Install it with {mgr}?", yes):
        raise SetupError("Xvfb is required")
    if install_packages([_PKG[mgr][1][1]], yes) != 0:
        raise SetupError("package installation failed")
    return shutil.which("Xvfb")


def _screen(yes: bool) -> None:
    """Linux without any display: make sure Xvfb exists for the silent installers."""
    if IS_LINUX and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        ensure_xvfb(yes)


def _wine_run(args: list, prefix: Path, show: bool = False) -> None:
    try:
        r = wineenv.run_wine(args, prefix, check=False, headless=True, stop=True, timeout=600, capture_output=not show, text=True)
    except subprocess.TimeoutExpired:
        raise SetupError(f"wine {' '.join(map(str, args))} timed out")
    if r.returncode != 0:
        raise SetupError(f"wine {' '.join(map(str, args))} failed: {(r.stderr or r.stdout or '').strip()[-400:]}")


def _install_terminal(exe: Path, prefix: Path, version: int, show: bool = True, directory: Path | None = None) -> Path:
    """Run the official setup silently on a virtual screen, then stop the terminal it launches; returns terminal64.exe."""
    pats = [f"Program Files{x}/MetaTrader {version}/terminal{y}.exe" for x in ("", " (x86)") for y in ("64", "")]
    found = lambda: (directory and _terminal_in(directory)) or next((h for pat in pats for h in sorted((prefix / "drive_c").glob(pat))), None)  # noqa: E731
    args = [exe, "/auto"] + ([f"/path:Z:{str(directory).replace('/', chr(92))}"] if directory else [])
    try:
        wineenv.run_wine(args, prefix, check=False, headless=True, stop=True, timeout=900, capture_output=not show, text=True, cwd=str(exe.parent))
    except subprocess.TimeoutExpired:
        pass
    t = found()
    if not t:
        raise SetupError(f"MetaTrader {version} was not found in {prefix} after the installer ran")
    return t


def _is_admin() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _terminal_in(d: Path) -> Path | None:
    return next((t for n in ("terminal64.exe", "terminal.exe") if (t := d / n).is_file()), None)


def _remember(directory: Path) -> None:
    cfg = config.load()
    cur = [x for x in str(cfg.get("search") or "").split(os.pathsep) if x]
    if str(directory) not in cur:
        cfg["search"] = os.pathsep.join([*cur, str(directory)])
        config.save(cfg)


def _windows_terminal(version: int, directory: Path | None = None) -> Path | None:
    if directory:
        return _terminal_in(directory)
    roots = [Path(v) for k in ("ProgramFiles", "ProgramFiles(x86)") if (v := os.environ.get(k))]
    names = ("terminal64.exe", "terminal.exe")
    return next((t for r in roots for n in names if (t := r / f"MetaTrader {version}" / n).is_file()), None)


def _stop_windows_terminal(t: Path) -> None:
    ps = f"Get-CimInstance Win32_Process | Where-Object {{ $_.ExecutablePath -eq '{t}' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, stdin=subprocess.DEVNULL, timeout=60, check=False)


def _install_windows(exe: Path, version: int, directory: Path | None = None) -> Path:
    """Run the official setup without a window and stop the terminal it launches; returns the installed terminal."""
    hidden = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if _is_admin():
        cmd = f'"{exe}" /auto' + (f' /path:"{directory}"' if directory else "")
    else:
        args = "'/auto'" + (f""", '/path:"{directory}"'""" if directory else "")
        ps = f"Start-Process -FilePath '{exe}' -ArgumentList @({args}) -Verb RunAs -WindowStyle Hidden -Wait"
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps]
    try:
        subprocess.run(cmd, cwd=str(exe.parent), stdin=subprocess.DEVNULL, creationflags=hidden, timeout=900, check=False)
    except subprocess.TimeoutExpired:
        pass
    t = _windows_terminal(version, directory)
    if not t:
        raise SetupError(f"MetaTrader {version} was not found in {directory or 'Program Files'} after the installer ran")
    _stop_windows_terminal(t)
    return t


def _packages(py: Path, prefix: Path, show: bool) -> None:
    _wine_run([py, "-m", "pip", "install", "--upgrade", "pip", "MetaTrader5", "numpy"], prefix, show)
    _wine_run([py, "-c", "import MetaTrader5"], prefix)


def _install_python(prefix: Path, show: bool) -> Path:
    """Install the default Windows Python (3.12) into the prefix and return its python.exe."""
    exe = config.home() / "downloads" / PYTHON_URL.rsplit("/", 1)[-1]
    exe.parent.mkdir(parents=True, exist_ok=True)
    if not exe.is_file():
        try:
            _get(PYTHON_URL, exe, show)
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise SetupError(f"could not download Windows Python: {e}") from e
    _wine_run([exe, "/quiet", "InstallAllUsers=0", f"TargetDir={PYTHON_DIR}", "PrependPath=0", "Include_test=0", "Include_launcher=0"], prefix, show)
    own = prefix / "drive_c" / PYTHON_DIR.split("\\", 1)[1] / "python.exe"
    py = own if own.is_file() else wineenv.wine_python(prefix)
    if not py:
        raise SetupError("Windows Python did not install into the prefix")
    return py


def setup_wine_python(prefix: str | Path, yes: bool = False, show: bool = True) -> Path:
    """Make a Windows Python with the MetaTrader5 package available in a Wine prefix; returns python.exe.

    A Python already in the prefix, wherever it lives, is used. When there is none, or MetaTrader5 cannot be
    installed into it (for example a Python version the package does not support), Python 3.12 is installed.
    """
    prefix = Path(prefix)
    ensure_wine(yes)
    _screen(yes)
    prefix.mkdir(parents=True, exist_ok=True)
    py = wineenv.wine_python(prefix)
    if py:
        try:
            _packages(py, prefix, show)
            return py
        except SetupError:
            if py.parent.name.lower() == PYTHON_DIR.split("\\")[-1].lower():
                raise
    _wine_run(["wineboot", "-u"], prefix)
    try:
        _wine_run(["reg.exe", "add", "HKCU\\Software\\Wine", "/v", "Version", "/d", "win10", "/f"], prefix)
    except SetupError:
        pass
    py = _install_python(prefix, show)
    _packages(py, prefix, show)
    return py


def install(version: int = 5, yes: bool = False, prefix: str | Path | None = None, method: str = "auto", directory: str | Path | None = None) -> None:
    """Install the terminal for this operating system.

    Linux methods: auto and wine run the official Windows installer silently under Wine on a virtual screen (no
    window opens; the prefix defaults to ~/.mt5 or ~/.mt4); script runs MetaQuotes' own shell script instead.
    """
    key = os_key()
    dest_dir = Path(directory).expanduser().resolve() if directory else None
    if dest_dir and not dest_dir.name.lower().startswith("metatrader"):
        dest_dir = dest_dir / f"MetaTrader{version}"
    if dest_dir and method == "script" and key == "linux":
        raise SetupError("a custom directory is not supported with the script method")
    if key == "windows":
        exe = download(version, key)
        if not ask("The installer needs administrator permission. Start it now?", yes):
            return
        t = _install_windows(exe, version, dest_dir)
        if dest_dir:
            _remember(dest_dir)
        print(f"installed {t}")
        return
    if key == "macos":
        dmg = download(version, key)
        mnt = Path(tempfile.mkdtemp(prefix="mtx-dmg-"))
        subprocess.check_call(["hdiutil", "attach", "-nobrowse", "-quiet", "-mountpoint", str(mnt), str(dmg)])
        try:
            apps = list(mnt.glob("*.app"))
            if apps:
                dest = (dest_dir or Path("/Applications")) / apps[0].name
                dest.parent.mkdir(parents=True, exist_ok=True)
                subprocess.check_call(["cp", "-R", str(apps[0]), str(dest)])
                if dest_dir:
                    _remember(dest_dir)
                print(f"installed {dest}")
            else:
                subprocess.call(["open", str(mnt)])
                input("Finish the installation in the opened window, then press Enter. ")
        finally:
            subprocess.call(["hdiutil", "detach", "-quiet", str(mnt)])
        return
    if method == "script":
        sh = download(version, key)
        sh.chmod(0o755)
        if not ask("The official script installs Wine and asks for your password (sudo). Run it now?", yes):
            return
        if subprocess.call(["bash", str(sh)], env=wineenv.base_env(), cwd=str(sh.parent)) != 0:
            raise SetupError("the installer script failed")
        return
    ensure_wine(yes)
    _screen(yes)
    pre = Path(prefix) if prefix else Path.home() / f".mt{version}"
    exe = download(version, "windows")
    pre.mkdir(parents=True, exist_ok=True)
    _wine_run(["wineboot", "-u"], pre)
    t = _install_terminal(exe, pre, version, directory=dest_dir) if dest_dir else _install_terminal(exe, pre, version)
    if dest_dir:
        _remember(dest_dir)
    print(f"installed {t}")


def platform_summary() -> dict:
    """Operating system, machine type, Python version and wine binary, as shown by `mtx doctor`."""
    return {"os": os_key(), "machine": platform.machine(), "python": sys.version.split()[0], "wine": wineenv.wine_bin()}
