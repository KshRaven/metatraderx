from __future__ import annotations

import http.server
import threading

from pathlib import Path

import pytest

from metatraderx import display
from metatraderx.cli import build_parser
from metatraderx.errors import SetupError


def _os(monkeypatch, win=False, mac=False, linux=False):
    monkeypatch.setattr(display, "IS_WIN", win)
    monkeypatch.setattr(display, "IS_MAC", mac)
    monkeypatch.setattr(display, "IS_LINUX", linux)


def test_find_xpra_on_path(monkeypatch):
    monkeypatch.setattr(display.shutil, "which", lambda n: "/usr/bin/xpra" if n == "xpra" else None)
    assert display.find_xpra() == "/usr/bin/xpra"


def test_find_xpra_missing(monkeypatch):
    _os(monkeypatch, linux=True)
    monkeypatch.setattr(display.shutil, "which", lambda n: None)
    assert display.find_xpra() is None


def test_status_keys_per_system(monkeypatch):
    monkeypatch.setattr(display, "find_xpra", lambda: None)
    monkeypatch.setattr(display, "find_cloudflared", lambda: None)
    monkeypatch.setattr(display, "_html5_dir", lambda: None)
    monkeypatch.setattr(display.shutil, "which", lambda n: None)
    monkeypatch.setattr(display.wineenv, "wine_bin", lambda: None)
    _os(monkeypatch, win=True)
    assert set(display.display_status()) == {"xpra"}
    _os(monkeypatch, linux=True)
    assert set(display.display_status(True)) == {"xpra", "xpra_html5", "xvfb", "wine", "cloudflared"}
    _os(monkeypatch, mac=True)
    assert set(display.display_status()) == {"xpra", "wine"}


def test_ensure_ready_declined(monkeypatch):
    _os(monkeypatch, linux=True)
    monkeypatch.setattr(display, "display_status", lambda tunnel=False: {"xpra": None, "wine": "/usr/bin/wine"})
    monkeypatch.setattr(display, "ask", lambda q, yes=False, default=True: False)
    with pytest.raises(SetupError, match="mtx display setup"):
        display._ensure_ready(False, False)


def test_ensure_ready_installs(monkeypatch):
    _os(monkeypatch, linux=True)
    calls = []
    monkeypatch.setattr(display, "display_status", lambda tunnel=False: {"xpra": None})
    monkeypatch.setattr(display, "ask", lambda q, yes=False, default=True: True)
    monkeypatch.setattr(display, "setup_display", lambda yes=False, tunnel=False: calls.append((yes, tunnel)) or {})
    monkeypatch.setattr(display, "_ensure_xpra", lambda yes: "/usr/bin/xpra")
    assert display._ensure_ready(False, True) == "/usr/bin/xpra"
    assert calls == [(True, True)]


def test_ensure_ready_nothing_missing(monkeypatch):
    monkeypatch.setattr(display, "display_status", lambda tunnel=False: {"xpra": "/x"})
    monkeypatch.setattr(display, "ask", lambda *a, **k: pytest.fail("should not ask"))
    monkeypatch.setattr(display, "_ensure_xpra", lambda yes: "/x")
    assert display._ensure_ready(False, False) == "/x"


def test_setup_display_order(monkeypatch):
    _os(monkeypatch, linux=True)
    order = []
    monkeypatch.setattr(display, "ensure_wine", lambda yes: order.append("wine"))
    monkeypatch.setattr(display, "ensure_xvfb", lambda yes: order.append("xvfb"))
    monkeypatch.setattr(display, "_ensure_xpra", lambda yes: order.append("xpra"))
    monkeypatch.setattr(display, "_ensure_cloudflared", lambda yes: order.append("cf"))
    monkeypatch.setattr(display, "display_status", lambda tunnel=False: {"xpra": "/x"})
    assert display.setup_display(True, True) == {"xpra": "/x"}
    assert order == ["wine", "xvfb", "xpra", "cf"]


def test_setup_display_windows_skips_wine(monkeypatch):
    _os(monkeypatch, win=True)
    order = []
    monkeypatch.setattr(display, "ensure_wine", lambda yes: order.append("wine"))
    monkeypatch.setattr(display, "ensure_xvfb", lambda yes: order.append("xvfb"))
    monkeypatch.setattr(display, "_ensure_xpra", lambda yes: order.append("xpra"))
    monkeypatch.setattr(display, "display_status", lambda tunnel=False: {})
    display.setup_display(True)
    assert order == ["xpra"]


def test_install_xpra_windows_winget(monkeypatch):
    _os(monkeypatch, win=True)
    seen = []
    monkeypatch.setattr(display.shutil, "which", lambda n: "winget" if n == "winget" else None)
    monkeypatch.setattr(display.subprocess, "call", lambda cmd, **k: seen.append(cmd) or 0)
    display._install_xpra(True)
    assert seen and "xpra-org.xpra" in seen[0] and "--silent" in seen[0]


def test_install_xpra_windows_falls_back_to_installer(monkeypatch):
    _os(monkeypatch, win=True)
    called = []
    monkeypatch.setattr(display.shutil, "which", lambda n: None)
    monkeypatch.setattr(display, "_install_xpra_exe", lambda yes: called.append(yes))
    display._install_xpra(True)
    assert called == [True]


def test_install_xpra_linux_packages(monkeypatch):
    _os(monkeypatch, linux=True)
    got = []
    monkeypatch.setattr(display, "_add_xpra_repo", lambda yes: True)
    monkeypatch.setattr(display, "install_packages", lambda pkgs, yes=False: got.append(pkgs) or 0)
    for mgr, want in (("apt-get", ["xpra", "xpra-html5"]), ("dnf", ["xpra", "xpra-html5"]), ("pacman", ["xpra"])):
        monkeypatch.setattr(display, "package_manager", lambda m=mgr: m)
        display._install_xpra(True)
        assert got[-1] == want


def test_install_xpra_linux_no_manager(monkeypatch):
    _os(monkeypatch, linux=True)
    monkeypatch.setattr(display, "package_manager", lambda: None)
    with pytest.raises(SetupError):
        display._install_xpra(True)


def test_install_xpra_mac(monkeypatch):
    _os(monkeypatch, mac=True)
    monkeypatch.setattr(display.shutil, "which", lambda n: None)
    with pytest.raises(SetupError, match="Homebrew"):
        display._install_xpra(True)
    seen = []
    monkeypatch.setattr(display.shutil, "which", lambda n: "/opt/homebrew/bin/brew")
    monkeypatch.setattr(display.subprocess, "call", lambda cmd, **k: seen.append(cmd) or 0)
    display._install_xpra(True)
    assert seen == [["brew", "install", "--cask", "xpra"]]


def test_install_xpra_exe_download(tmp_path, monkeypatch):
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", "3")
            self.end_headers()
            self.wfile.write(b"exe")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("MTX_HOME", str(tmp_path))
    monkeypatch.setenv("MTX_URL_XPRA_WINDOWS", f"http://127.0.0.1:{srv.server_address[1]}/Xpra_Setup.exe")
    seen = []
    monkeypatch.setattr(display, "ask", lambda *a, **k: True)
    monkeypatch.setattr(display.subprocess, "call", lambda cmd, **k: seen.append(cmd) or 0)
    try:
        display._install_xpra_exe(True)
    finally:
        srv.shutdown()
    assert (tmp_path / "downloads" / "Xpra_Setup.exe").read_bytes() == b"exe"
    assert "/VERYSILENT" in seen[0]


def test_install_xpra_exe_all_downloads_fail(tmp_path, monkeypatch):
    monkeypatch.setenv("MTX_HOME", str(tmp_path))
    monkeypatch.setattr(display, "_get", lambda *a, **k: (_ for _ in ()).throw(ValueError("no")))
    with pytest.raises(SetupError, match="xpra.org"):
        display._install_xpra_exe(True)


def test_ensure_xpra_html5_warning(monkeypatch, capsys):
    _os(monkeypatch, linux=True)
    monkeypatch.setattr(display, "find_xpra", lambda: "/usr/bin/xpra")
    monkeypatch.setattr(display, "_html5_dir", lambda: None)
    monkeypatch.setattr(display, "ask", lambda *a, **k: True)
    monkeypatch.setattr(display, "_install_xpra", lambda yes: None)
    assert display._ensure_xpra(True) == "/usr/bin/xpra"
    assert "xpra-html5" in capsys.readouterr().err


def test_ensure_xpra_declined(monkeypatch):
    _os(monkeypatch, win=True)
    monkeypatch.setattr(display, "find_xpra", lambda: None)
    monkeypatch.setattr(display, "ask", lambda *a, **k: False)
    with pytest.raises(SetupError, match="mtx display setup"):
        display._ensure_xpra(False)


def test_display_parser():
    p = build_parser()
    a = p.parse_args(["display"])
    assert a.action == "run" and a.port is None and not a.tunnel
    a = p.parse_args(["display", "setup", "--tunnel", "-y"])
    assert a.action == "setup" and a.tunnel and a.yes


def test_install_xpra_apt_adds_repo(monkeypatch):
    _os(monkeypatch, linux=True)
    order = []
    monkeypatch.setattr(display, "package_manager", lambda: "apt-get")
    monkeypatch.setattr(display, "_add_xpra_repo", lambda yes: order.append("repo") or True)
    monkeypatch.setattr(display, "install_packages", lambda pkgs, yes=False: order.append("pkg") or 0)
    display._install_xpra(True)
    assert order == ["repo", "pkg"]
    monkeypatch.setattr(display, "install_packages", lambda pkgs, yes=False: 100)
    with pytest.raises(SetupError, match="could not install Xpra"):
        display._install_xpra(True)


def _repo_env(monkeypatch, tmp_path, codename="plucky", py=13, fits=("trixie",)):
    lst = tmp_path / "xpra.sources"
    monkeypatch.setattr(display, "_XPRA_LIST", lst)
    monkeypatch.setattr(display, "_codename", lambda: codename)
    monkeypatch.setattr(display, "_distro", lambda: {"ubuntu", "debian"})
    monkeypatch.setattr(display, "_system_python_minor", lambda: py)
    state = {"suite": None, "urls": [], "sudo": []}

    def get(url, dest, show):
        state["urls"].append(url)
        dest.write_text(url)

    def sudo(cmd, yes):
        state["sudo"].append(cmd)
        if cmd[0] == "install" and cmd[-1] == str(lst):
            lst.write_text(Path(cmd[-2]).read_text())
        if cmd[0] == "rm":
            lst.unlink(missing_ok=True)
        return 0

    monkeypatch.setattr(display, "_get", get)
    monkeypatch.setattr(display, "_sudo", sudo)
    monkeypatch.setattr(display, "ask", lambda *a, **k: True)
    monkeypatch.setattr(display, "_apt_can_install", lambda pkgs: any(f"/repos/{f}/" in lst.read_text() for f in fits) if lst.is_file() else False)
    return lst, state


def test_add_xpra_repo_guards(monkeypatch, tmp_path):
    lst, st = _repo_env(monkeypatch, tmp_path)
    monkeypatch.setattr(display, "_codename", lambda: None)
    assert display._add_xpra_repo(True) is False
    monkeypatch.setattr(display, "_codename", lambda: "plucky")
    monkeypatch.setattr(display, "_distro", lambda: {"fedora"})
    assert display._add_xpra_repo(True) is False


def test_add_xpra_repo_skips_releases_that_do_not_fit(monkeypatch, tmp_path):
    lst, st = _repo_env(monkeypatch, tmp_path)
    assert display._add_xpra_repo(True) is True
    assert "/repos/trixie/" in lst.read_text()
    assert any("/repos/plucky/" in u for u in st["urls"])


def test_add_xpra_repo_none_fits(monkeypatch, tmp_path):
    lst, st = _repo_env(monkeypatch, tmp_path, fits=())
    assert display._add_xpra_repo(True) is False
    assert not lst.exists()


def test_add_xpra_repo_keeps_working_repo_and_replaces_broken_one(monkeypatch, tmp_path):
    lst, st = _repo_env(monkeypatch, tmp_path)
    lst.write_text("/repos/trixie/")
    assert display._add_xpra_repo(True) is True and not st["urls"]
    lst.write_text("/repos/noble/")
    assert display._add_xpra_repo(True) is True and "/repos/trixie/" in lst.read_text()


def test_add_xpra_repo_declined_or_key_missing(monkeypatch, tmp_path):
    lst, st = _repo_env(monkeypatch, tmp_path)
    monkeypatch.setattr(display, "ask", lambda *a, **k: False)
    assert display._add_xpra_repo(False) is False and not lst.exists()
    monkeypatch.setattr(display, "_get", lambda *a: (_ for _ in ()).throw(display.urllib.error.URLError("off")))
    assert display._add_xpra_repo(True) is False


def test_xpra_suites(monkeypatch):
    monkeypatch.setattr(display, "_distro", lambda: {"ubuntu", "debian"})
    monkeypatch.setattr(display, "_system_python_minor", lambda: 13)
    assert display._xpra_suites("plucky")[:2] == ["plucky", "trixie"]
    monkeypatch.setattr(display, "_system_python_minor", lambda: 12)
    assert display._xpra_suites("noble") == ["noble", "jammy", "resolute", "trixie"]
    monkeypatch.setattr(display, "_distro", lambda: {"debian"})
    assert display._xpra_suites("trixie")[0] == "trixie" and "bookworm" in display._xpra_suites("trixie")
