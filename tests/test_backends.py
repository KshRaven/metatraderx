from __future__ import annotations
import json
import os
import socket
import stat
import sys
import threading
import types
import urllib.request
from pathlib import Path

import pytest

from metatraderx import MetaTrader, _worker, codec, wineenv
from metatraderx.backends.base import API, TRADING, Backend
from metatraderx.backends.native import NativeBackend
from metatraderx.backends.remote import RemoteBackend, parse_url
from metatraderx.backends.wine import WineBackend
from metatraderx.errors import AuthError, BackendError, MTXError, RemoteError, SetupError
from metatraderx.server import MTXServer, is_loopback

FAKE_MT5 = """
__version__ = "9.9.9"
def initialize(*a, **k): return (a, k)
def shutdown(): return True
def symbols_total(): return 7
def boom(): raise RuntimeError("bad")
_hidden = 1
value = 3
"""


@pytest.fixture
def fake_mt5(monkeypatch):
    m = types.ModuleType("MetaTrader5")
    exec(FAKE_MT5, m.__dict__)
    monkeypatch.setitem(sys.modules, "MetaTrader5", m)
    return m


def test_base_backend():
    b = Backend()
    assert b.alive and b.name == "base" and not b.remote
    with pytest.raises(NotImplementedError):
        b.call("x", (), {})
    b.close()
    assert set(TRADING) <= set(API) and len(API) == len(set(API))


def test_native_backend(fake_mt5):
    be = NativeBackend()
    assert be.call("symbols_total", (), {}) == 7
    assert be.call("initialize", (1,), {"a": 2}) == ((1,), {"a": 2})
    with pytest.raises(AttributeError):
        be.call("missing", (), {})


def test_native_backend_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)
    with pytest.raises(SetupError):
        NativeBackend()


def test_worker_loop(fake_mt5, monkeypatch):
    lst = socket.socket()
    lst.bind(("127.0.0.1", 0))
    lst.listen(1)
    monkeypatch.setattr(sys, "argv", ["w", str(lst.getsockname()[1]), "nonce1"])
    res = {}
    t = threading.Thread(target=lambda: res.setdefault("rc", _worker.main()))
    t.start()
    conn, _ = lst.accept()
    hello = codec.unpack(codec.recv_frame(conn))
    assert hello["nonce"] == "nonce1" and hello["version"] == "9.9.9"

    def rpc(m, a=(), k=None):
        codec.send_frame(conn, codec.pack({"m": m, "a": a, "k": k or {}}))
        return codec.unpack(codec.recv_frame(conn))

    assert rpc("__ping__")["r"] is True
    assert rpc("symbols_total")["r"] == 7
    assert rpc("boom")["t"] == "RuntimeError"
    assert rpc("_hidden")["ok"] is False
    assert rpc("value")["ok"] is False
    assert rpc("nope")["t"] == "AttributeError"
    codec.send_frame(conn, codec.pack({"m": "__quit__"}))
    t.join(5)
    assert res["rc"] == 0
    conn.close()
    lst.close()


def test_worker_reports_missing_package(monkeypatch):
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)
    lst = socket.socket()
    lst.bind(("127.0.0.1", 0))
    lst.listen(1)
    monkeypatch.setattr(sys, "argv", ["w", str(lst.getsockname()[1]), "n"])
    res = {}
    t = threading.Thread(target=lambda: res.setdefault("rc", _worker.main()))
    t.start()
    conn, _ = lst.accept()
    assert "unavailable" in codec.unpack(codec.recv_frame(conn))["error"]
    t.join(5)
    assert res["rc"] == 2
    conn.close()
    lst.close()


def _fake_wine(tmp_path):
    """A wine stand-in: runs the worker with the host python, with a fake MetaTrader5 on its path."""
    mod = tmp_path / "mods"
    mod.mkdir()
    (mod / "MetaTrader5.py").write_text(FAKE_MT5)
    wine = tmp_path / "wine"
    wine.write_text(f'#!/bin/sh\nshift\nPYTHONPATH="{mod}" exec "{sys.executable}" "$@"\n')
    wp = tmp_path / "winepath"
    wp.write_text('#!/bin/sh\necho "$2"\n')
    for f in (wine, wp):
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    py = tmp_path / "python.exe"
    py.write_text("")
    return wine, py


@pytest.mark.skipif(sys.platform == "win32", reason="uses a shell script as wine")
def test_wine_backend_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("DISPLAY", ":0")
    wine, py = _fake_wine(tmp_path)
    be = WineBackend(prefix=str(tmp_path), wine=str(wine), python=str(py), startup_timeout=30)
    assert not be.alive
    with pytest.raises(BackendError):
        be.call("symbols_total", (), {})
    be.start()
    try:
        assert be.alive and be.info["version"] == "9.9.9"
        be.start()
        assert be.call("symbols_total", (), {}) == 7
        out = be.call("initialize", (), {"path": "/some/terminal64.exe"})
        assert out[1]["path"] == "/some/terminal64.exe"
        with pytest.raises(BackendError):
            be.call("boom", (), {})
    finally:
        be.close()
    assert not be.alive


@pytest.mark.skipif(sys.platform == "win32", reason="uses a shell script as wine")
def test_wine_backend_start_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(wineenv, "wine_bin", lambda: None)
    with pytest.raises(SetupError, match="prefix"):
        WineBackend().start()
    with pytest.raises(SetupError, match="wine was not found"):
        WineBackend(prefix=str(tmp_path)).start()
    with pytest.raises(SetupError, match="Windows Python"):
        WineBackend(prefix=str(tmp_path), wine="/bin/true", python=str(tmp_path / "none.exe")).start()


@pytest.mark.skipif(sys.platform == "win32", reason="uses a shell script as wine")
def test_wine_backend_worker_never_connects(tmp_path, monkeypatch):
    monkeypatch.setenv("DISPLAY", ":0")
    wine, py = _fake_wine(tmp_path)
    idle = tmp_path / "idle"
    idle.write_text("#!/bin/sh\nsleep 5\n")
    idle.chmod(0o755)
    be = WineBackend(prefix=str(tmp_path), wine=str(idle), python=str(py), startup_timeout=0.5)
    monkeypatch.setattr(wineenv, "to_win_path", lambda *a: "w")
    with pytest.raises(BackendError, match="in time"):
        be.start()


def test_wineenv_helpers(tmp_path, monkeypatch):
    monkeypatch.setenv("MTX_HOME", str(tmp_path / "h"))
    for k in ("MTX_WINE", "MTX_WINE_PYTHON"):
        monkeypatch.delenv(k, raising=False)
    exe = tmp_path / "mywine"
    exe.write_text("")
    monkeypatch.setenv("MTX_WINE", str(exe))
    assert wineenv.wine_bin() == str(exe)
    monkeypatch.setenv("MTX_WINE", "")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(wineenv, "IS_MAC", False)
    assert wineenv.wine_bin() is None
    env = wineenv.base_env(tmp_path)
    assert env["WINEPREFIX"] == str(tmp_path) and env["WINEDEBUG"]
    assert wineenv.wine_python(None) is None
    assert wineenv.wine_python(tmp_path) is None
    p = tmp_path / "drive_c" / "Python312" / "python.exe"
    p.parent.mkdir(parents=True)
    p.write_text("")
    assert wineenv.wine_python(tmp_path) == p
    q = tmp_path / "py.exe"
    q.write_text("")
    monkeypatch.setenv("MTX_WINE_PYTHON", str(q))
    assert wineenv.wine_python(tmp_path) == q
    with pytest.raises(SetupError):
        wineenv.run_wine(["--version"], tmp_path)


@pytest.mark.skipif(sys.platform == "win32", reason="posix shell")
def test_to_win_path_and_display(tmp_path, monkeypatch):
    ok = tmp_path / "winepath"
    ok.write_text('#!/bin/sh\necho junk\necho "Z:$2"\n')
    ok.chmod(0o755)
    wine = tmp_path / "wine"
    wine.write_text("")
    assert wineenv.to_win_path(str(wine), os.environ.copy(), "/a/b") == "Z:/a/b"
    ok.write_text("#!/bin/sh\nexit 3\n")
    with pytest.raises(SetupError):
        wineenv.to_win_path(str(wine), os.environ.copy(), "/a/b")
    monkeypatch.setenv("DISPLAY", ":1")
    assert wineenv.ensure_display() == ({}, None)
    monkeypatch.delenv("DISPLAY")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "nothing"))
    monkeypatch.setattr(wineenv, "IS_LINUX", True)
    assert wineenv.ensure_display() == ({}, None)
    monkeypatch.setattr(wineenv, "IS_LINUX", False)
    assert wineenv.ensure_display() == ({}, None)


def test_run_wine(tmp_path, monkeypatch):
    if sys.platform == "win32":
        pytest.skip("posix shell")
    w = tmp_path / "wine"
    w.write_text('#!/bin/sh\necho "$1 $WINEPREFIX"\n')
    w.chmod(0o755)
    monkeypatch.setenv("MTX_WINE", str(w))
    monkeypatch.setenv("DISPLAY", ":0")
    r = wineenv.run_wine(["hi"], tmp_path, capture_output=True, text=True)
    assert r.stdout.strip() == f"hi {tmp_path}"


def test_parse_url():
    assert parse_url("mtx://h:1") == (False, "h", 1, "")
    assert parse_url("h") == (False, "h", 8765, "")
    assert parse_url("https://d.example/base/") == (True, "d.example", 443, "/base")
    assert parse_url("mtxs://d:9") == (True, "d", 9, "")


def test_is_loopback():
    assert is_loopback("localhost") and is_loopback("127.0.0.1") and is_loopback("::1") and is_loopback("")
    assert not is_loopback("0.0.0.0") and not is_loopback("example.com")


class Stub(Backend):
    name = "stub"

    def __init__(self):
        self.calls = []

    def call(self, m, a, k):
        self.calls.append(m)
        return {"symbols_total": 3, "login": True, "order_send": "sent", "order_check": "ok"}.get(m)


def _srv(**kw):
    mt = MetaTrader(strict=True)
    mt._backend = Stub()
    return mt, MTXServer(mt, "127.0.0.1", 0, **kw).start()


def test_server_rules():
    mt, s = _srv(read_only=True)
    try:
        be = RemoteBackend(f"127.0.0.1:{s.port}")
        assert be.call("symbols_total", (), {}) == 3
        for m in ("order_send", "order_check", "login", "initialize", "shutdown", "nonsense"):
            with pytest.raises(RemoteError):
                be.call(m, (), {})
        assert "order_send" not in mt._backend.calls
    finally:
        s.stop()
    mt, s = _srv(allow_login=True)
    try:
        assert RemoteBackend(f"127.0.0.1:{s.port}").call("login", (1,), {}) is True
        assert RemoteBackend(f"127.0.0.1:{s.port}").call("order_send", ({},), {}) == "sent"
    finally:
        s.stop()


def test_server_http_edges():
    mt, s = _srv(token="t")
    try:
        base = f"http://127.0.0.1:{s.port}"

        def status(req):
            try:
                return urllib.request.urlopen(req, timeout=5).status
            except urllib.error.HTTPError as e:
                return e.code

        assert status(base + "/health") == 401
        assert status(urllib.request.Request(base + "/health", headers={"Authorization": "Bearer t"})) == 200
        assert status(base + "/other") == 404
        h = {"Authorization": "Bearer t"}
        assert status(urllib.request.Request(base + "/nope", data=b"x", headers=h)) == 404
        assert status(urllib.request.Request(base + "/rpc", data=b"x")) == 401
        body = json.loads(urllib.request.urlopen(urllib.request.Request(base + "/health", headers=h)).read())
        assert body["status"] == "ok" and body["backend"] == "stub"
        garbage = urllib.request.Request(base + "/rpc", data=b"garbage-bytes", headers=h)
        resp = codec.unpack(urllib.request.urlopen(garbage).read())
        assert resp["ok"] is False
    finally:
        s.stop()


def test_remote_errors():
    with pytest.raises(AuthError):
        mt, s = _srv(token="a")
        try:
            RemoteBackend(f"127.0.0.1:{s.port}", token="b").call("symbols_total", (), {})
        finally:
            s.stop()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    be = RemoteBackend(f"127.0.0.1:{port}", timeout=1)
    assert be.ping() is False
    with pytest.raises(BackendError):
        be.call("symbols_total", (), {})
    be.close()


def test_server_start_stop_and_guard():
    mt = MetaTrader()
    with pytest.raises(MTXError):
        MTXServer(mt, "0.0.0.0", 0)
    s = MTXServer(mt, "0.0.0.0", 0, token="x")
    s.httpd.server_close()
    assert s.tls is False


def test_client_offline_without_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MTX_HOME", str(tmp_path))
    mt = MetaTrader(offline=True)
    assert mt.initialize() is True and mt.symbols_total() is None
    mt.shutdown()


def test_winedebug_levels(monkeypatch, tmp_path):
    monkeypatch.setenv("MTX_HOME", str(tmp_path))
    monkeypatch.delenv("MTX_WINEDEBUG", raising=False)
    monkeypatch.delenv("WINEDEBUG", raising=False)
    assert wineenv.winedebug() == "-all"
    monkeypatch.setenv("WINEDEBUG", "err+all")
    assert wineenv.winedebug() == "err+all"
    for given, want in (("all", "-all"), ("fixme", "fixme-all"), ("off", ""), ("+timestamp", "+timestamp")):
        monkeypatch.setenv("MTX_WINEDEBUG", given)
        assert wineenv.winedebug() == want
        assert wineenv.base_env()["WINEDEBUG"] == want


def test_ensure_display_force(monkeypatch):
    monkeypatch.setattr(wineenv, "IS_LINUX", True)
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setattr(wineenv.shutil, "which", lambda n: None)
    assert wineenv.ensure_display(True) == ({}, None)


@pytest.mark.skipif(sys.platform == "win32", reason="posix shell")
def test_run_wine_settles_before_closing_the_screen(tmp_path, monkeypatch):
    w = tmp_path / "wine"
    w.write_text("#!/bin/sh\ntrue\n")
    w.chmod(0o755)
    ws = tmp_path / "wineserver"
    ws.write_text('#!/bin/sh\necho "$1" >> "%s"\n' % (tmp_path / "log"))
    ws.chmod(0o755)
    monkeypatch.setenv("MTX_WINE", str(w))
    monkeypatch.setattr(wineenv, "IS_LINUX", True)

    class P:
        terminated = False

        def terminate(self):
            self.terminated = True

    proc = P()
    monkeypatch.setattr(wineenv, "ensure_display", lambda force=False: ({"DISPLAY": ":9"}, proc))
    wineenv.run_wine(["x"], tmp_path, headless=True)
    wineenv.run_wine(["x"], tmp_path, headless=True, stop=True)
    assert (tmp_path / "log").read_text().split() == ["-w", "-k"] and proc.terminated


def test_worker_socket_has_no_idle_timeout():
    src = (Path(__file__).resolve().parent.parent / "metatraderx" / "_worker.py").read_text()
    assert "create_connection" in src and "sock.settimeout(None)" in src


def test_wine_pythons_found_anywhere(tmp_path, monkeypatch):
    monkeypatch.setenv("MTX_WINE_PYTHON", "")
    c = tmp_path / "drive_c"
    a = c / "tools" / "Python311" / "python.exe"
    b = c / "py" / "deep" / "Python313" / "python.exe"
    u = c / "users" / "me" / "AppData" / "Local" / "Programs" / "Python" / "Python312" / "python.exe"
    skip = c / "Python311" / "Lib" / "venv" / "python.exe"
    for f in (a, b, u, skip):
        f.parent.mkdir(parents=True)
        f.write_text("")
    found = wineenv.wine_pythons(tmp_path)
    assert a in found and u in found and b in found and skip not in found
    assert wineenv.wine_python(tmp_path) == found[0]
    pkg = u.parent / "Lib" / "site-packages" / "MetaTrader5"
    pkg.mkdir(parents=True)
    assert wineenv.has_metatrader5(u) and not wineenv.has_metatrader5(a)
    assert wineenv.wine_python(tmp_path) == u
    assert wineenv.wine_pythons(None) == []
