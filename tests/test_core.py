from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from metatraderx import MetaTrader, codec
from metatraderx.backends.base import Backend
from metatraderx.backends.remote import RemoteBackend
from metatraderx.cache import Cache
from metatraderx.errors import AuthError, RemoteError
from metatraderx.export import parse_dt, to_rows
from metatraderx.server import MTXServer
from metatraderx.types import RECORDS, Tick

RATES = np.dtype([("time", "<i8"), ("open", "<f8"), ("close", "<f8")])


class Fake(Backend):
    name = "fake"

    def __init__(self) -> None:
        self.calls: list = []

    def call(self, method, args, kwargs):
        self.calls.append(method)
        if method == "symbols_total":
            return 3
        if method == "copy_rates_range":
            return np.array([(1, 1.5, 1.6), (2, 1.6, 1.7)], dtype=RATES)
        if method == "symbol_info_tick":
            return Tick(1, 1.0, 1.1, 0.0, 0, 1000, 6, 0.0)
        return None


def test_codec_roundtrip():
    arr = np.array([(1, 1.5, 1.6)], dtype=RATES)
    now = datetime(2024, 1, 2, 3, 4, tzinfo=timezone.utc)
    obj = {"a": arr, "t": Tick(1, 1.0, 1.1, 0.0, 0, 1000, 6, 0.0), "d": now, "x": (1, "a"), "n": None}
    out = codec.unpack(codec.pack(obj), RECORDS)
    assert out["a"].dtype == arr.dtype and out["a"].tolist() == arr.tolist()
    assert isinstance(out["t"], Tick) and out["t"].ask == 1.1
    assert out["d"] == now and out["x"] == (1, "a") and out["n"] is None


def test_cache_roundtrip(tmp_path):
    c = Cache(tmp_path)
    c.put("k", "m", (1, 2))
    assert c.get("k")[0] == (1, 2)
    assert c.clear() == 1 and c.get("k") is None
    c.close()


def test_client_cache(tmp_path):
    mt = MetaTrader(cache=True, cache_dir=tmp_path)
    mt._backend = Fake()
    assert mt.symbols_total() == 3 and mt.symbols_total() == 3
    assert mt._backend.calls.count("symbols_total") == 1
    a, b = datetime(2020, 1, 1), datetime(2020, 1, 2)
    mt.copy_rates_range("EURUSD", 1, a, b)
    assert len(mt.copy_rates_range("EURUSD", 1, a, b)) == 2
    assert mt._backend.calls.count("copy_rates_range") == 1


def test_cache_off_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("MTX_CACHE", raising=False)
    mt = MetaTrader()
    mt._backend = Fake()
    mt.symbols_total()
    mt.symbols_total()
    assert mt._backend.calls.count("symbols_total") == 2


def test_server_remote():
    mt = MetaTrader(strict=True)
    mt._backend = Fake()
    srv = MTXServer(mt, "127.0.0.1", 0, token="tok").start()
    try:
        be = RemoteBackend(f"mtx://127.0.0.1:{srv.port}", token="tok")
        assert be.ping()
        assert be.call("symbols_total", (), {}) == 3
        assert be.call("symbol_info_tick", ("EURUSD",), {}).bid == 1.0
        with pytest.raises(RemoteError):
            be.call("initialize", (), {})
        with pytest.raises(AuthError):
            RemoteBackend(f"mtx://127.0.0.1:{srv.port}", token="bad").call("symbols_total", (), {})
    finally:
        srv.stop()


def test_server_needs_token_off_loopback():
    with pytest.raises(Exception):
        MTXServer(MetaTrader(), "0.0.0.0", 0)


def test_export():
    rows = to_rows(np.array([(1700000000, 1.5, 1.6)], dtype=RATES))
    assert rows[0]["time"].endswith("Z") and rows[0]["open"] == 1.5
    assert parse_dt("2024-01-31").tzinfo is not None


def test_offline_module(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MTX_HOME", str(tmp_path))
    from metatraderx.backends.base import Backend
    from metatraderx.client import MetaTrader

    class Fake(Backend):
        def call(self, m, a, k):
            return True if m == "initialize" else 7 if m == "symbols_total" else None

    on = MetaTrader(cache=True)
    on._backend = Fake()
    assert on.symbols_total() == 7
    off = MetaTrader(offline=True, verbose=0)
    assert off.initialize() and off.login(1) and off.symbols_total() == 7
    assert capsys.readouterr().err == ""
    loud = MetaTrader(offline=True, verbose=1)
    loud.initialize()
    assert "offline mode" in capsys.readouterr().err
    import metatraderx.offline as mt5

    assert mt5.default().offline and mt5.initialize() and hasattr(mt5, "copy_rates_from_pos")


def test_native_record_roundtrip():
    from collections import namedtuple

    from metatraderx import codec

    class Native(tuple):
        def _asdict(self):
            return {"a": self[0], "b": self[1]}

    Native.__name__ = "TerminalInfo"
    out = codec.unpack(codec.pack({"r": Native((1, 2))}))["r"]
    assert out._fields == ("a", "b") and out.b == 2 and isinstance(out, tuple)
    assert namedtuple


def test_symbol_names_and_frame(tmp_path, monkeypatch):
    monkeypatch.setenv("MTX_HOME", str(tmp_path))
    from collections import namedtuple

    from metatraderx.backends.base import Backend
    from metatraderx.client import MetaTrader

    S = namedtuple("SymbolInfo", ["name"])

    class Fake(Backend):
        def call(self, m, a, k):
            return [S("EURUSD"), S("XAUUSD"), S("BTCUSDm")] if m == "symbols_get" else True

    mt = MetaTrader()
    mt._backend = Fake()
    assert mt.symbol_names() == ["EURUSD", "XAUUSD", "BTCUSDm"]
    assert mt.symbol_names(first=2) == ["EURUSD", "XAUUSD"]
    assert mt.symbol_names(last=1) == ["BTCUSDm"]
    assert hasattr(mt, "to_frame")


def test_find_terminals_mapped_drive(tmp_path, monkeypatch):
    pre = tmp_path / "pre"
    (pre / "drive_c").mkdir(parents=True)
    (pre / "dosdevices").mkdir()
    d = tmp_path / "ddrive" / "Apps" / "MT5" / "MQL5"
    d.mkdir(parents=True)
    (d.parent / "terminal64.exe").write_bytes(b"")
    try:
        (pre / "dosdevices" / "d:").symlink_to(tmp_path / "ddrive")
    except OSError:
        return
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("WINEPREFIX", str(pre))
    monkeypatch.setenv("MTX_HOME", str(tmp_path / "h"))
    from metatraderx import discovery

    if discovery.IS_WIN:
        return
    found = discovery.find_terminals()
    assert any(t["path"].endswith("terminal64.exe") and t["version"] == 5 for t in found)
    assert discovery.prefix_of(found[0]["path"]) == pre
