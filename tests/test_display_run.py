from __future__ import annotations

import io
import runpy
import subprocess
import sys

import pytest

import metatraderx.offline as off
from metatraderx import display
from metatraderx.errors import SetupError


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MTX_HOME", str(tmp_path / "h"))
    monkeypatch.setenv("HOME", str(tmp_path / "u"))
    monkeypatch.setattr(display.time, "sleep", lambda s: None)


def _os(monkeypatch, win=False, mac=False, linux=False):
    monkeypatch.setattr(display, "IS_WIN", win)
    monkeypatch.setattr(display, "IS_MAC", mac)
    monkeypatch.setattr(display, "IS_LINUX", linux)


def test_find_xpra_windows_and_mac(monkeypatch, tmp_path):
    monkeypatch.setattr(display.shutil, "which", lambda n: None)
    _os(monkeypatch, win=True)
    exe = tmp_path / "pf" / "Xpra" / "Xpra_cmd.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "pf"))
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    assert display.find_xpra() == str(exe)
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "none"))
    assert display.find_xpra() is None
    _os(monkeypatch, mac=True)
    assert display.find_xpra() is None


def test_html5_dir(monkeypatch, tmp_path):
    d = tmp_path / "www"
    d.mkdir()
    monkeypatch.setattr(display, "_HTML5_DIRS", (str(tmp_path / "x"), str(d)))
    assert display._html5_dir() == str(d)
    monkeypatch.setattr(display, "_HTML5_DIRS", (str(tmp_path / "x"),))
    assert display._html5_dir() is None


def test_find_cloudflared(monkeypatch, tmp_path):
    monkeypatch.setattr(display.shutil, "which", lambda n: "/bin/cf")
    assert display.find_cloudflared() == "/bin/cf"
    monkeypatch.setattr(display.shutil, "which", lambda n: None)
    _os(monkeypatch, linux=True)
    assert display.find_cloudflared() is None
    b = display.config.home() / "bin"
    b.mkdir(parents=True)
    (b / "cloudflared").write_bytes(b"")
    assert display.find_cloudflared() == str(b / "cloudflared")


def test_ensure_cloudflared_found(monkeypatch):
    monkeypatch.setattr(display, "find_cloudflared", lambda: "/cf")
    assert display._ensure_cloudflared(True) == "/cf"


def test_ensure_cloudflared_mac(monkeypatch):
    _os(monkeypatch, mac=True)
    state = {"cf": None}
    monkeypatch.setattr(display, "find_cloudflared", lambda: state["cf"])
    monkeypatch.setattr(display.shutil, "which", lambda n: None)
    with pytest.raises(SetupError, match="brew install"):
        display._ensure_cloudflared(True)
    monkeypatch.setattr(display.shutil, "which", lambda n: "/brew")
    monkeypatch.setattr(display, "ask", lambda *a, **k: False)
    with pytest.raises(SetupError, match="required"):
        display._ensure_cloudflared(False)
    monkeypatch.setattr(display, "ask", lambda *a, **k: True)
    ran = []
    monkeypatch.setattr(display.subprocess, "call", lambda c: ran.append(c))
    with pytest.raises(SetupError, match="did not install"):
        display._ensure_cloudflared(True)
    monkeypatch.setattr(display.subprocess, "call", lambda c: state.update(cf="/cf"))
    assert display._ensure_cloudflared(True) == "/cf" and ran == [["brew", "install", "cloudflared"]]


@pytest.mark.parametrize("machine,win,expect", [("x86_64", False, "cloudflared-linux-amd64"), ("aarch64", False, "cloudflared-linux-arm64"), ("AMD64", True, "cloudflared-windows-amd64.exe")])
def test_ensure_cloudflared_download(monkeypatch, tmp_path, machine, win, expect):
    _os(monkeypatch, win=win, linux=not win)
    monkeypatch.setattr(display, "find_cloudflared", lambda: None)
    monkeypatch.setattr(display.platform, "machine", lambda: machine)
    monkeypatch.setattr(display, "ask", lambda *a, **k: False)
    with pytest.raises(SetupError, match="required"):
        display._ensure_cloudflared(False)
    monkeypatch.setattr(display, "ask", lambda *a, **k: True)
    got = {}
    monkeypatch.setattr(display.urllib.request, "urlretrieve", lambda url, dest: (got.update(url=url), dest.write_bytes(b"x")))
    path = display._ensure_cloudflared(True)
    assert got["url"].endswith(expect) and path.endswith("cloudflared.exe" if win else "cloudflared")


def test_tunnel_prints_link(monkeypatch, capsys):
    class P:
        stdout = io.StringIO("noise\nhttps://abc-def.trycloudflare.com ready\n")

    monkeypatch.setattr(display.subprocess, "Popen", lambda *a, **k: P())
    display._tunnel("/cf", 14500)
    import time

    for _ in range(50):
        if "public link" in capsys.readouterr().out:
            break
        time.sleep(0.05)
    else:
        pytest.fail("no link printed")


class Proc:
    made: list = []

    def __init__(self, cmd, **kw):
        self.cmd, self.kw, self.polls, self.terminated, self.returncode = cmd, kw, 0, False, 0
        Proc.made.append(self)

    def poll(self):
        if self.terminated:
            return 0
        self.polls += 1
        return None if self.polls < 3 else self.returncode

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


@pytest.fixture
def procs(monkeypatch):
    Proc.made = []
    monkeypatch.setattr(display.subprocess, "Popen", Proc)
    monkeypatch.setattr(display, "_ensure_ready", lambda y, t: "/bin/xpra")
    monkeypatch.setattr(display, "_port_free", lambda h, p: True)
    monkeypatch.setattr(display, "_terminal_running", lambda t: False)
    return Proc.made


def test_serve_display_linux(monkeypatch, procs, tmp_path, capsys):
    _os(monkeypatch, linux=True)
    monkeypatch.setattr(display.wineenv, "wine_bin", lambda: "/usr/bin/wine")
    pre = tmp_path / "pre"
    (pre / "drive_c").mkdir(parents=True)
    exe = pre / "drive_c" / "terminal64.exe"
    exe.write_bytes(b"")
    monkeypatch.setenv("MTX_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(display, "_terminal_running", lambda t: False)
    assert display.serve_display(str(exe)) == 0
    cmd = procs[0].cmd
    assert cmd[:2] == ["/bin/xpra", "start"] and "--html=on" in cmd and "--daemon=no" in cmd
    assert any(c.startswith("--start-child=") and "wine" in c and "terminal.log" in c for c in cmd)
    assert not any(c.startswith("--tcp-auth") for c in cmd)
    assert procs[0].kw["env"]["WINEPREFIX"] == str(pre)
    assert "terminal display: http://127.0.0.1:14500/" in capsys.readouterr().out


def test_serve_display_public_generates_password(monkeypatch, procs, capsys, tmp_path):
    _os(monkeypatch, linux=True)
    monkeypatch.setattr(display.wineenv, "wine_bin", lambda: "/usr/bin/wine")
    monkeypatch.setenv("MTX_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(display, "_terminal_running", lambda t: False)
    display.serve_display("/x/terminal64.exe", host="0.0.0.0")
    out = capsys.readouterr().out
    assert "password:" in out and "http://127.0.0.1:14500/" in out
    assert "--tcp-auth=env" in procs[0].cmd and procs[0].kw["env"]["XPRA_PASSWORD"] in out


def test_serve_display_given_password_not_printed(monkeypatch, procs, capsys):
    _os(monkeypatch, linux=True)
    monkeypatch.setattr(display.wineenv, "wine_bin", lambda: "/usr/bin/wine")
    display.serve_display("/x/t.exe", password="mine")
    assert "password:" not in capsys.readouterr().out and procs[0].kw["env"]["XPRA_PASSWORD"] == "mine"


def test_serve_display_needs_wine(monkeypatch, procs):
    _os(monkeypatch, linux=True)
    monkeypatch.setattr(display.wineenv, "wine_bin", lambda: None)
    with pytest.raises(SetupError, match="wine"):
        display.serve_display("/x/t.exe")


def test_serve_display_windows_shadow(monkeypatch, procs, tmp_path):
    _os(monkeypatch, win=True)
    exe = tmp_path / "terminal64.exe"
    display.serve_display(str(exe))
    assert procs[0].cmd == [str(exe)] and procs[1].cmd[:2] == ["/bin/xpra", "shadow"]
    assert all(p.terminated or p.polls >= 1 for p in procs)


def test_serve_display_tunnel(monkeypatch, procs):
    _os(monkeypatch, linux=True)
    monkeypatch.setattr(display.wineenv, "wine_bin", lambda: "/usr/bin/wine")
    monkeypatch.setattr(display, "_ensure_cloudflared", lambda y: "/cf")
    monkeypatch.setattr(display, "_tunnel", lambda cf, port: Proc([cf, "tunnel"]))
    display.serve_display("/x/t.exe", tunnel=True)
    assert procs[0].cmd == ["/cf", "tunnel"] and procs[0].terminated


def test_serve_display_keyboard_interrupt(monkeypatch, procs):
    _os(monkeypatch, linux=True)
    monkeypatch.setattr(display.wineenv, "wine_bin", lambda: "/usr/bin/wine")

    def boom(s):
        raise KeyboardInterrupt

    monkeypatch.setattr(display.time, "sleep", boom)
    assert display.serve_display("/x/t.exe") == 0
    assert procs[0].terminated


def test_serve_display_kills_stubborn_process(monkeypatch, procs):
    _os(monkeypatch, linux=True)
    monkeypatch.setattr(display.wineenv, "wine_bin", lambda: "/usr/bin/wine")
    killed = []

    class Stubborn(Proc):
        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired("x", 1)

        def kill(self):
            killed.append(1)

    monkeypatch.setattr(display.subprocess, "Popen", Stubborn)
    display.serve_display("/x/t.exe")
    assert killed


def test_ensure_ready_and_setup_chain(monkeypatch):
    _os(monkeypatch, linux=True)
    calls = []
    monkeypatch.setattr(display, "ensure_wine", lambda y: calls.append("wine"))
    monkeypatch.setattr(display, "ensure_xvfb", lambda y: calls.append("xvfb"))
    monkeypatch.setattr(display, "_ensure_xpra", lambda y: calls.append("xpra") or "/x")
    monkeypatch.setattr(display, "_ensure_cloudflared", lambda y: calls.append("cf"))
    monkeypatch.setattr(display, "display_status", lambda t=False: {"xpra": "/x"})
    display.setup_display(True, True)
    assert calls == ["wine", "xvfb", "xpra", "cf"]


def test_offline_module(monkeypatch, tmp_path):
    assert off.default().offline
    assert off.symbols_total.__doc__ == off.MetaTrader.symbols_total.__doc__
    cfg = off.configure(cache_dir=tmp_path / "c", verbose=0)
    assert cfg.offline and off.default() is cfg
    assert off.initialize() is True
    assert off.symbols_total() is None
    assert off.symbol_names() is None
    off.shutdown()
    assert hasattr(off, "TIMEFRAME_H1") and hasattr(off, "SetupError") and hasattr(off, "Tick")


def test_python_dash_m_main(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["metatraderx", "--version"])
    with pytest.raises(SystemExit) as e:
        runpy.run_module("metatraderx", run_name="__main__")
    assert e.value.code == 0
    assert "mtx" in capsys.readouterr().out


def test_pick_port(monkeypatch):
    busy = {14500, 14501}
    monkeypatch.setattr(display, "_port_free", lambda h, p: p not in busy)
    assert display.pick_port("127.0.0.1") == 14502
    assert display.pick_port("127.0.0.1", 15000) == 15000
    with pytest.raises(SetupError):
        display.pick_port("127.0.0.1", 14500)
    monkeypatch.setattr(display, "_port_free", lambda h, p: False)
    with pytest.raises(SetupError):
        display.pick_port("127.0.0.1")


def test_serve_display_refuses_running_terminal(monkeypatch, procs, tmp_path):
    _os(monkeypatch, linux=True)
    monkeypatch.setattr(display.wineenv, "wine_bin", lambda: "/usr/bin/wine")
    monkeypatch.setattr(display, "_terminal_running", lambda t: True)
    with pytest.raises(SetupError, match="already running"):
        display.serve_display("/x/terminal64.exe")


def test_serve_display_force_stops_terminal(monkeypatch, procs, tmp_path):
    _os(monkeypatch, linux=True)
    monkeypatch.setattr(display.wineenv, "wine_bin", lambda: "/usr/bin/wine")
    monkeypatch.setenv("MTX_HOME", str(tmp_path / "home"))
    stopped = []
    monkeypatch.setattr(display, "_stop_terminal", lambda t: stopped.append(t))
    monkeypatch.setattr(display, "_terminal_running", lambda t: False)
    display.serve_display("/x/terminal64.exe", force=True)
    assert stopped == ["/x/terminal64.exe"]


def test_stop_terminal_kills_prefix(monkeypatch, tmp_path):
    _os(monkeypatch, linux=True)
    killed = []
    monkeypatch.setattr(display, "prefix_of", lambda t: tmp_path)
    monkeypatch.setattr(display.wineenv, "kill_server", lambda p: killed.append(p))
    monkeypatch.setattr(display, "_terminal_running", lambda t: False)
    display._stop_terminal("/x/terminal64.exe")
    assert killed == [tmp_path]
