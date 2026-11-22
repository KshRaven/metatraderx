from __future__ import annotations

import json
import socket
import threading
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pytest

from metatraderx import MetaTrader, config, wineenv
from metatraderx import constants as C
from metatraderx.backends import mt4
from metatraderx.backends.mt4 import MT4Backend, install_bridge
from metatraderx.errors import BackendError, SetupError

SYMS = [{"name": "EURUSD", "digits": 5}, {"name": "XAUUSD", "digits": 2}, {"name": "GBPUSD", "digits": 5}]
TRADE = {
    "ticket": 7, "open_time": 1700000000, "type": 0, "magic": 1, "volume": 0.1, "open_price": 1.1, "sl": 0.0,
    "tp": 0.0, "close_price": 1.2, "swap": 0.0, "profit": 5.0, "symbol": "EURUSD", "comment": "c", "commission": -1.0,
    "close_time": 1700000100,
}
PENDING = {**TRADE, "ticket": 8, "type": 2}


def handlers():
    return {
        "terminal_info": {"build": 1400, "name": "MT4"},
        "account_info": {"login": 5, "server": "S"},
        "symbols": SYMS,
        "symbol_info": SYMS[0],
        "tick": {"bid": 1.0, "ask": 1.1},
        "symbol_select": True,
        "rates_pos": [[1, 1.0, 2.0, 0.5, 1.5, 10, 2, 0]],
        "rates_range": [[1, 1.0, 2.0, 0.5, 1.5, 10, 2, 0], [2, 1.5, 2.0, 1.0, 1.7, 11, 2, 0]],
        "open_trades": [TRADE, PENDING],
        "history": [TRADE, PENDING],
    }


class Bridge:
    """A stand-in for the MetaTraderXBridge expert."""

    def __init__(self, port, table):
        self.table, self.seen = table, []
        self.sock = socket.create_connection(("127.0.0.1", port), 5)
        self.t = threading.Thread(target=self.loop, daemon=True)
        self.t.start()

    def loop(self):
        buf = b""
        while True:
            try:
                d = self.sock.recv(65536)
            except OSError:
                return
            if not d:
                return
            buf += d
            while b"\n" in buf:
                line, _, buf = buf.partition(b"\n")
                _, m, *args = line.decode().split("|")
                self.seen.append((m, args))
                out = {"ok": True, "r": self.table[m]} if m in self.table else {"ok": False, "e": f"no {m}"}
                self.sock.sendall((json.dumps(out) + "\n").encode())

    def close(self):
        self.sock.close()


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture
def be():
    port = free_port()
    b = MT4Backend(port)
    b._listener = socket.socket()
    b._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    b._listener.bind(("127.0.0.1", port))
    b._listener.listen(1)
    bridge = Bridge(port, handlers())
    assert b._bridge_up(5)
    yield b, bridge
    bridge.close()
    b.close()


def test_helpers():
    assert mt4._ts(5) == 5
    assert mt4._ts(datetime(1970, 1, 1, 0, 1, tzinfo=timezone.utc)) == 60
    assert mt4._ts(datetime(1970, 1, 1, 0, 1)) == 60
    assert mt4._rates([]) is None and mt4._rates(None) is None
    arr = mt4._rates([[1, 1.0, 2.0, 0.5, 1.5, 10, 2, 0]])
    assert arr.dtype == mt4.RATES_DTYPE and arr["close"][0] == 1.5


def test_default_port(monkeypatch, tmp_path):
    monkeypatch.setenv("MTX_HOME", str(tmp_path))
    monkeypatch.delenv("MTX_MT4_PORT", raising=False)
    assert MT4Backend().port == 5555
    monkeypatch.setenv("MTX_MT4_PORT", "6000")
    assert MT4Backend().port == 6000
    assert MT4Backend(7000).port == 7000
    assert not MT4Backend().alive


def test_data_calls(be):
    b, bridge = be
    assert b.alive
    assert b.call("account_info", (), {}).login == 5
    assert b.call("terminal_info", (), {}).build == 1400
    assert b.call("version", (), {}) == (4, 1400, "")
    assert b.call("symbols_total", (), {}) == 3
    assert [s.name for s in b.call("symbols_get", (), {})] == ["EURUSD", "XAUUSD", "GBPUSD"]
    assert [s.name for s in b.call("symbols_get", ("*USD*,!XAU*",), {})] == ["EURUSD", "GBPUSD"]
    assert [s.name for s in b.call("symbols_get", (), {"group": "XAU*"})] == ["XAUUSD"]
    assert b.call("symbol_info", ("EURUSD",), {}).digits == 5
    assert b.call("symbol_info_tick", ("EURUSD",), {}).bid == 1.0
    assert b.call("symbol_select", ("EURUSD", False), {}) is True
    assert ("symbol_select", ["EURUSD", "0"]) in bridge.seen
    r = b.call("copy_rates_from_pos", ("EURUSD", C.TIMEFRAME_H1, 0, 1), {})
    assert r.dtype == mt4.RATES_DTYPE and ("rates_pos", ["EURUSD", "60", "0", "1"]) in bridge.seen
    d1, d2 = datetime(2024, 1, 1, tzinfo=timezone.utc), 1704153600
    r = b.call("copy_rates_range", ("EURUSD", C.TIMEFRAME_D1, d1, d2), {})
    assert len(r) == 2 and ("rates_range", ["EURUSD", "1440", "1704067200", "1704153600"]) in bridge.seen
    assert b.call("last_error", (), {}) == (1, "Success")


def test_positions_and_history(be):
    b, _ = be
    pos = b.call("positions_get", (), {})
    assert len(pos) == 1 and pos[0].ticket == 7 and pos[0].price_current == 1.2
    assert b.call("positions_get", (), {"symbol": "GBPUSD"}) is None
    assert b.call("positions_total", (), {}) == 1
    deals = b.call("history_deals_get", (0, 10**10), {})
    assert len(deals) == 1 and deals[0].commission == -1.0
    assert b.call("history_deals_get", (), {"group": "XAU*"}) is None
    assert b.call("history_deals_total", (0, 10**10), {}) == 1


def test_unsupported_and_login(be):
    b, _ = be
    with pytest.raises(BackendError, match="not supported"):
        b.call("order_send", ({},), {})
    with pytest.raises(BackendError, match="login"):
        b.call("login", (1,), {})


def test_bridge_error_and_drop(be):
    b, bridge = be
    bridge.table.pop("tick")
    with pytest.raises(BackendError, match="no tick"):
        b.call("symbol_info_tick", ("X",), {})
    bridge.close()
    with pytest.raises(BackendError, match="dropped"):
        b.call("symbols_total", (), {})
    assert not b.alive


def test_rpc_without_bridge_times_out(monkeypatch):
    b = MT4Backend(free_port())
    b._listener = socket.socket()
    b._listener.bind(("127.0.0.1", b.port))
    b._listener.listen(1)
    monkeypatch.setattr(b, "_bridge_up", lambda t: False)
    with pytest.raises(BackendError, match="not connected"):
        b.call("symbols_total", (), {})
    b.close()


def test_start_flow(monkeypatch):
    port = free_port()
    b = MT4Backend(port)
    launched = []
    monkeypatch.setattr(b, "_launch", lambda p: launched.append(p) or setattr(b, "_proc", object()))
    with pytest.raises(BackendError, match="did not connect"):
        b.start("/x/terminal.exe", 0.2)
    assert launched == ["/x/terminal.exe"]
    threading.Thread(target=lambda: Bridge(port, handlers()), daemon=True).start()
    b.start(None, 5)
    assert b.alive
    b._proc = None
    assert b.call("initialize", ("/p",), {"timeout": 1}) is True
    b.close()
    assert not b.alive


def test_launch_windows_and_wine(monkeypatch, tmp_path):
    started = []

    class P:
        def __init__(self, cmd, **k):
            started.append((cmd, k))

        def terminate(self):
            started.append("terminated")

    monkeypatch.setattr(mt4.subprocess, "Popen", P)
    b = MT4Backend(free_port())
    monkeypatch.setattr(config, "IS_WIN", True)
    b._launch(str(tmp_path / "terminal.exe"))
    assert started[0][0] == [str(tmp_path / "terminal.exe")]
    monkeypatch.setattr(config, "IS_WIN", False)
    monkeypatch.setattr(wineenv, "wine_bin", lambda: None)
    with pytest.raises(SetupError):
        b._launch("/x/terminal.exe")
    monkeypatch.setattr(wineenv, "wine_bin", lambda: "/usr/bin/wine")
    monkeypatch.setenv("DISPLAY", ":0")
    b._launch("/x/terminal.exe")
    assert started[-1][0] == ["/usr/bin/wine", "/x/terminal.exe"]
    b.close()
    assert started[-1] == "terminated"


def test_install_bridge_local_and_prefix(tmp_path, monkeypatch):
    exe = tmp_path / "MT4" / "terminal.exe"
    (exe.parent / "MQL4").mkdir(parents=True)
    exe.write_bytes(b"")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "ad"))
    out = install_bridge(str(exe))
    assert out == [exe.parent / "MQL4" / "Experts" / "MetaTraderXBridge.mq4"]
    assert out[0].read_text() == mt4.BRIDGE.read_text()
    pre = tmp_path / "pre"
    app = pre / "drive_c" / "Program Files" / "MT4" / "terminal.exe"
    app.parent.mkdir(parents=True)
    app.write_bytes(b"")
    data = pre / "drive_c" / "users" / "u" / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "H" / "MQL4"
    data.mkdir(parents=True)
    assert install_bridge(str(app)) == [data / "Experts" / "MetaTraderXBridge.mq4"]


def test_install_bridge_nothing_found(tmp_path, monkeypatch):
    exe = tmp_path / "t" / "terminal.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.setattr(config, "IS_WIN", False)
    with pytest.raises(SetupError, match="no MQL4"):
        install_bridge(str(exe))


def test_bridge_source_is_shipped():
    assert mt4.BRIDGE.is_file() and mt4.BRIDGE.stat().st_size > 100


def test_client_mt4_through_metatrader(be):
    b, _ = be
    mt = MetaTrader(strict=True)
    mt._backend = b
    assert mt.symbol_names(first=1) == ["EURUSD"]
    assert np.asarray(mt.copy_rates_from_pos("EURUSD", C.TIMEFRAME_H1, 0, 1)).dtype == mt4.RATES_DTYPE
    assert mt.version()[0] == 4
