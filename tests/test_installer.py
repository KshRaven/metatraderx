from __future__ import annotations

import io
import subprocess
import urllib.error

import pytest

from metatraderx import installer, wineenv
from metatraderx.errors import SetupError


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MTX_HOME", str(tmp_path / "h"))
    return tmp_path


def _sys(monkeypatch, win=False, mac=False):
    for mod in (installer, wineenv):
        monkeypatch.setattr(mod, "IS_WIN", win, raising=False)
        monkeypatch.setattr(mod, "IS_MAC", mac, raising=False)


def test_os_key(monkeypatch):
    _sys(monkeypatch, win=True)
    assert installer.os_key() == "windows"
    _sys(monkeypatch, mac=True)
    assert installer.os_key() == "macos"
    _sys(monkeypatch)
    assert installer.os_key() == "linux"


def test_candidate_urls(monkeypatch):
    monkeypatch.delenv("MTX_URL_MT5_LINUX", raising=False)
    urls = installer.candidate_urls(5, "linux")
    assert urls[0].startswith("https://download.mql5.com") and all(u.startswith("https://") for u in urls)
    monkeypatch.setenv("MTX_URL_MT5_LINUX", "https://mine/x.sh")
    assert installer.candidate_urls(5, "linux")[0] == "https://mine/x.sh"
    assert any("mt4setup" in u for u in installer.candidate_urls(4, "windows"))


def test_ask(monkeypatch):
    assert installer.ask("q", yes=True)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert installer.ask("q", default=True) is True and installer.ask("q", default=False) is False

    class TTY(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr("sys.stdin", TTY())
    for answer, default, out in (("", True, True), ("", False, False), ("y", False, True), ("no", True, False)):
        monkeypatch.setattr("builtins.input", lambda *_a, a=answer: a)
        assert installer.ask("q", default=default) is out


class Resp:
    def __init__(self, body=b"data", ctype="application/octet-stream"):
        self.body, self.headers = io.BytesIO(body), {"Content-Type": ctype, "Content-Length": str(len(body))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n):
        return self.body.read(n)


def test_get_and_download(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=0: Resp(b"x" * 10))
    out = installer.download(5, "windows", tmp_path / "d")
    assert out.read_bytes() == b"x" * 10 and out.name == "mt5setup.exe"
    assert "100%" in capsys.readouterr().err


def test_download_falls_through_and_fails(monkeypatch, tmp_path):
    calls = []

    def fake(req, timeout=0):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise urllib.error.URLError("down")
        return Resp(b"ok")

    monkeypatch.setattr("urllib.request.urlopen", fake)
    out = installer.download(5, "windows", tmp_path, show=False)
    assert out.read_bytes() == b"ok" and len(calls) == 2
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: Resp(b"<html>", "text/html"))
    with pytest.raises(SetupError, match="HTML"):
        installer.download(5, "windows", tmp_path / "b", show=False)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("x")))
    with pytest.raises(SetupError, match="could not download"):
        installer.download(5, "windows", tmp_path / "c", show=False)
    assert not list((tmp_path / "c").glob("*"))


def test_distro(tmp_path, monkeypatch):
    f = tmp_path / "os-release"
    f.write_text('ID=ubuntu\nID_LIKE="debian other"\n')
    real = installer.Path
    monkeypatch.setattr(installer, "Path", lambda p: f if p == "/etc/os-release" else real(p))
    assert installer._distro() == {"ubuntu", "debian", "other"}
    monkeypatch.setattr(installer, "Path", lambda p: tmp_path / "missing")
    assert installer._distro() == set()


def test_sudo(monkeypatch):
    cmds = []
    monkeypatch.setattr(subprocess, "call", lambda c, **k: cmds.append(c) or 0)
    monkeypatch.setattr(installer.os, "geteuid", lambda: 0, raising=False)
    assert installer._sudo(["a"], True) == 0 and cmds[-1] == ["a"]
    monkeypatch.setattr(installer.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr(installer.shutil, "which", lambda n: "/usr/bin/sudo")
    installer._sudo(["a"], True)
    assert cmds[-1] == ["sudo", "a"]
    monkeypatch.setattr(installer.shutil, "which", lambda n: None)
    with pytest.raises(SetupError):
        installer._sudo(["a"], True)


def test_package_manager_and_install(monkeypatch):
    monkeypatch.setattr(installer.shutil, "which", lambda n: "/x" if n == "dnf" else None)
    assert installer.package_manager() == "dnf"
    seen = []
    monkeypatch.setattr(installer, "_sudo", lambda c, y: seen.append(c) or 0)
    assert installer.install_packages(["wine"], True) == 0 and seen == [["dnf", "install", "-y", "wine"]]
    monkeypatch.setattr(installer.shutil, "which", lambda n: "/x" if n == "apt-get" else None)
    seen.clear()
    installer.install_packages(["wine"], True)
    assert seen[0] == ["apt-get", "update"] and seen[1][:3] == ["apt-get", "install", "-y"]
    monkeypatch.setattr(installer.shutil, "which", lambda n: None)
    with pytest.raises(SetupError, match="no supported package manager"):
        installer.install_packages(["wine"])


def test_ensure_wine_paths(monkeypatch):
    monkeypatch.setattr(wineenv, "wine_bin", lambda: "/w")
    assert installer.ensure_wine() == "/w"
    monkeypatch.setattr(wineenv, "wine_bin", lambda: None)
    _sys(monkeypatch, win=True)
    with pytest.raises(SetupError, match="not used on Windows"):
        installer.ensure_wine()
    _sys(monkeypatch, mac=True)
    monkeypatch.setattr(installer.shutil, "which", lambda n: None)
    with pytest.raises(SetupError, match="Homebrew"):
        installer.ensure_wine()
    monkeypatch.setattr(installer.shutil, "which", lambda n: "/brew")
    monkeypatch.setattr(installer, "ask", lambda *a, **k: False)
    with pytest.raises(SetupError, match="required"):
        installer.ensure_wine()
    monkeypatch.setattr(installer, "ask", lambda *a, **k: True)
    ran = []
    monkeypatch.setattr(subprocess, "call", lambda c, **k: ran.append(c))
    with pytest.raises(SetupError, match="not on PATH"):
        installer.ensure_wine()
    assert ran == [["brew", "install", "--cask", "wine-stable"]]


def test_ensure_wine_linux(monkeypatch):
    _sys(monkeypatch)
    state = {"w": None}
    monkeypatch.setattr(wineenv, "wine_bin", lambda: state["w"])
    monkeypatch.setattr(installer, "package_manager", lambda: None)
    with pytest.raises(SetupError, match="no supported package manager"):
        installer.ensure_wine()
    monkeypatch.setattr(installer, "package_manager", lambda: "apt-get")
    monkeypatch.setattr(installer, "ask", lambda *a, **k: False)
    with pytest.raises(SetupError, match="required"):
        installer.ensure_wine()
    monkeypatch.setattr(installer, "ask", lambda *a, **k: True)
    monkeypatch.setattr(installer, "install_packages", lambda p, y: 1)
    with pytest.raises(SetupError, match="failed"):
        installer.ensure_wine()
    monkeypatch.setattr(installer, "install_packages", lambda p, y: state.update(w="/w") or 0)
    assert installer.ensure_wine() == "/w"


def test_ensure_xvfb(monkeypatch):
    _sys(monkeypatch, win=True)
    assert installer.ensure_xvfb() is None
    _sys(monkeypatch)
    monkeypatch.setattr(installer.shutil, "which", lambda n: "/usr/bin/Xvfb")
    assert installer.ensure_xvfb() == "/usr/bin/Xvfb"
    monkeypatch.setattr(installer.shutil, "which", lambda n: None)
    monkeypatch.setattr(installer, "package_manager", lambda: None)
    with pytest.raises(SetupError, match="no supported"):
        installer.ensure_xvfb()
    monkeypatch.setattr(installer, "package_manager", lambda: "apt-get")
    monkeypatch.setattr(installer, "ask", lambda *a, **k: False)
    with pytest.raises(SetupError, match="required"):
        installer.ensure_xvfb()
    monkeypatch.setattr(installer, "ask", lambda *a, **k: True)
    got = []
    monkeypatch.setattr(installer, "install_packages", lambda p, y: got.append(p) or 1)
    with pytest.raises(SetupError, match="failed"):
        installer.ensure_xvfb()
    assert got == [["xvfb"]]
    monkeypatch.setattr(installer, "install_packages", lambda p, y: 0)
    assert installer.ensure_xvfb() is None


def test_wine_run_error(monkeypatch, tmp_path):
    cp = subprocess.CompletedProcess([], 1, stdout="", stderr="bad thing")
    monkeypatch.setattr(wineenv, "run_wine", lambda *a, **k: cp)
    with pytest.raises(SetupError, match="bad thing"):
        installer._wine_run(["x"], tmp_path)
    monkeypatch.setattr(wineenv, "run_wine", lambda *a, **k: subprocess.CompletedProcess([], 0))
    installer._wine_run(["x"], tmp_path)


def test_setup_wine_python_flow(monkeypatch, tmp_path):
    monkeypatch.setattr(installer, "ensure_wine", lambda y: "/w")
    monkeypatch.setattr(installer, "_screen", lambda y: None)
    runs = []
    monkeypatch.setattr(installer, "_wine_run", lambda a, p, s=False: runs.append([str(x) for x in a]))
    pre = tmp_path / "pre"
    exe = pre / "drive_c" / "Python312" / "python.exe"
    state = {"installed": False}

    def fake_py(prefix):
        return exe if state["installed"] else None

    monkeypatch.setattr(wineenv, "wine_python", fake_py)
    monkeypatch.setattr(installer, "_get", lambda url, dest, show: (dest.write_bytes(b"x"), state.update(installed=True)))
    assert installer.setup_wine_python(pre, True, False) == exe
    assert runs[0] == ["wineboot", "-u"] and any("InstallAllUsers=0" in " ".join(r) for r in runs)
    assert runs[-1][1:] == ["-c", "import MetaTrader5"]
    runs.clear()
    assert installer.setup_wine_python(pre, True, False) == exe
    assert [r[1] for r in runs] == ["-m", "-c"]


def test_setup_wine_python_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(installer, "ensure_wine", lambda y: "/w")
    monkeypatch.setattr(installer, "_screen", lambda y: None)
    monkeypatch.setattr(installer, "_wine_run", lambda *a, **k: None)
    monkeypatch.setattr(wineenv, "wine_python", lambda p: None)

    def down(*a):
        raise urllib.error.URLError("off")

    monkeypatch.setattr(installer, "_get", down)
    with pytest.raises(SetupError, match="download Windows Python"):
        installer.setup_wine_python(tmp_path / "p", True, False)
    monkeypatch.setattr(installer, "_get", lambda url, dest, show: dest.write_bytes(b"x"))
    with pytest.raises(SetupError, match="did not install"):
        installer.setup_wine_python(tmp_path / "p", True, False)


def test_install_windows(monkeypatch, tmp_path):
    _sys(monkeypatch, win=True)
    monkeypatch.setattr(installer, "download", lambda v, k: tmp_path / "setup.exe")
    ran = []
    monkeypatch.setattr(subprocess, "call", lambda c, **k: ran.append(c))
    monkeypatch.setattr(installer, "ask", lambda *a, **k: False)
    installer.install(5, False)
    assert not ran
    monkeypatch.setattr(installer, "ask", lambda *a, **k: True)
    installer.install(5, True)
    assert ran[0][1] == "/auto"


def test_install_macos(monkeypatch, tmp_path):
    _sys(monkeypatch, mac=True)
    monkeypatch.setattr(installer, "download", lambda v, k: tmp_path / "x.dmg")
    mnt = tmp_path / "mnt"
    mnt.mkdir()
    (mnt / "MetaTrader 5.app").mkdir()
    monkeypatch.setattr(installer.tempfile, "mkdtemp", lambda prefix="": str(mnt))
    cmds = []
    monkeypatch.setattr(subprocess, "check_call", lambda c: cmds.append(c))
    monkeypatch.setattr(subprocess, "call", lambda c, **k: cmds.append(c))
    installer.install(5, True)
    assert cmds[0][0] == "hdiutil" and cmds[1][:2] == ["cp", "-R"] and cmds[-1][1] == "detach"
    (mnt / "MetaTrader 5.app").rmdir()
    cmds.clear()
    monkeypatch.setattr("builtins.input", lambda *_: "")
    installer.install(5, True)
    assert cmds[1][0] == "open"


def test_install_linux_script(monkeypatch, tmp_path):
    _sys(monkeypatch)
    sh = tmp_path / "mt5linux.sh"
    sh.write_text("")
    monkeypatch.setattr(installer, "download", lambda v, k: sh)
    monkeypatch.setattr(installer, "ask", lambda *a, **k: False)
    calls = []
    monkeypatch.setattr(subprocess, "call", lambda c, **k: calls.append(c) or 0)
    installer.install(5, False, method="script")
    assert not calls
    monkeypatch.setattr(installer, "ask", lambda *a, **k: True)
    installer.install(5, True, method="script")
    assert calls == [["bash", str(sh)]]
    monkeypatch.setattr(subprocess, "call", lambda c, **k: 1)
    with pytest.raises(SetupError, match="script failed"):
        installer.install(5, True, method="script")


def test_install_linux_headless_wine(monkeypatch, tmp_path):
    _sys(monkeypatch)
    monkeypatch.setattr(installer, "ensure_wine", lambda y: "/w")
    monkeypatch.setattr(installer, "_screen", lambda y: None)
    monkeypatch.setattr(installer, "download", lambda v, k: tmp_path / "mt4setup.exe")
    runs = []
    monkeypatch.setattr(installer, "_wine_run", lambda a, p, s=False: runs.append((list(map(str, a)), p)))
    seen = {}
    monkeypatch.setattr(installer, "_install_terminal", lambda exe, pre, v, show=True: seen.update(exe=exe, pre=pre, v=v) or pre / "t.exe")
    installer.install(4, True, prefix=tmp_path / "pre")
    assert runs[0][0] == ["wineboot", "-u"] and (tmp_path / "pre").is_dir()
    assert seen["pre"] == tmp_path / "pre" and seen["v"] == 4
    monkeypatch.setattr(installer.Path, "home", classmethod(lambda cls: tmp_path))
    installer.install(5, True)
    assert seen["pre"] == tmp_path / ".mt5"


def test_install_terminal_headless(monkeypatch, tmp_path):
    runs = []
    pre = tmp_path / "pre"
    exe = pre / "drive_c" / "Program Files" / "MetaTrader 5" / "terminal64.exe"

    def fake(args, prefix, check=True, headless=False, stop=False, **kw):
        runs.append((list(map(str, args)), headless, kw.get("timeout"), stop))
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_text("")
        raise subprocess.TimeoutExpired("wine", 1)

    monkeypatch.setattr(wineenv, "run_wine", fake)
    assert installer._install_terminal(tmp_path / "s.exe", pre, 5) == exe
    assert runs[0][0][1] == "/auto" and runs[0][1] is True and runs[0][2] == 900 and runs[0][3] is True
    exe.unlink()
    monkeypatch.setattr(wineenv, "run_wine", lambda *a, **k: subprocess.CompletedProcess([], 0))
    with pytest.raises(SetupError, match="not found"):
        installer._install_terminal(tmp_path / "s.exe", pre, 5)


def test_screen_needs_xvfb_only_without_display(monkeypatch):
    _sys(monkeypatch)
    monkeypatch.setattr(installer, "IS_LINUX", True)
    calls = []
    monkeypatch.setattr(installer, "ensure_xvfb", lambda y: calls.append(y))
    monkeypatch.setenv("DISPLAY", ":0")
    installer._screen(True)
    assert not calls
    monkeypatch.delenv("DISPLAY")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    installer._screen(True)
    assert calls == [True]


def test_platform_summary():
    s = installer.platform_summary()
    assert set(s) == {"os", "machine", "python", "wine"}


def test_install_terminal_finds_mt4_exe(monkeypatch, tmp_path):
    pre = tmp_path / "pre"
    exe = pre / "drive_c" / "Program Files (x86)" / "MetaTrader 4" / "terminal.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    monkeypatch.setattr(wineenv, "run_wine", lambda *a, **k: subprocess.CompletedProcess([], 0))
    assert installer._install_terminal(tmp_path / "s.exe", pre, 4) == exe


def test_get_incomplete_download_leaves_nothing(monkeypatch, tmp_path):
    class Short(Resp):
        def __init__(self):
            super().__init__(b"abc")
            self.headers["Content-Length"] = "10"

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=0: Short())
    dest = tmp_path / "f.exe"
    with pytest.raises(ValueError, match="incomplete"):
        installer._get("http://x/f.exe", dest, False)
    assert not dest.exists() and not (tmp_path / "f.exe.part").exists()


def test_setup_uses_foreign_python_when_it_works(monkeypatch, tmp_path):
    monkeypatch.setattr(installer, "ensure_wine", lambda y: "/w")
    monkeypatch.setattr(installer, "_screen", lambda y: None)
    runs = []
    monkeypatch.setattr(installer, "_wine_run", lambda a, p, s=False: runs.append([str(x) for x in a]))
    py = tmp_path / "drive_c" / "anywhere" / "Python313" / "python.exe"
    monkeypatch.setattr(wineenv, "wine_python", lambda p: py)
    assert installer.setup_wine_python(tmp_path, True, False) == py
    assert [r[1] for r in runs] == ["-m", "-c"]


def test_setup_installs_default_python_when_packages_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(installer, "ensure_wine", lambda y: "/w")
    monkeypatch.setattr(installer, "_screen", lambda y: None)
    monkeypatch.setenv("MTX_HOME", str(tmp_path / "h"))
    runs = []
    foreign = tmp_path / "drive_c" / "x" / "Python314" / "python.exe"

    def run(a, p, s=False):
        a = [str(x) for x in a]
        runs.append(a)
        if a[0] == str(foreign) and a[1] == "-m":
            raise SetupError("no matching distribution")

    monkeypatch.setattr(installer, "_wine_run", run)
    monkeypatch.setattr(wineenv, "wine_python", lambda p: foreign)
    monkeypatch.setattr(installer, "_get", lambda url, dest, show: dest.write_bytes(b"x"))
    own = tmp_path / "drive_c" / "Python312" / "python.exe"
    own.parent.mkdir(parents=True)
    own.write_text("")
    assert installer.setup_wine_python(tmp_path, True, False) == own
    assert any("InstallAllUsers=0" in " ".join(r) for r in runs) and runs[-1][1:] == ["-c", "import MetaTrader5"]


def test_setup_reraises_when_own_python_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(installer, "ensure_wine", lambda y: "/w")
    monkeypatch.setattr(installer, "_screen", lambda y: None)
    own = tmp_path / "drive_c" / "Python312" / "python.exe"
    monkeypatch.setattr(wineenv, "wine_python", lambda p: own)

    def run(a, p, s=False):
        raise SetupError("offline")

    monkeypatch.setattr(installer, "_wine_run", run)
    with pytest.raises(SetupError, match="offline"):
        installer.setup_wine_python(tmp_path, True, False)
