from __future__ import annotations

from collections import namedtuple
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

import metatraderx as mtx
from metatraderx import MetaTrader, config
from metatraderx import constants as C
from metatraderx.backends.base import API, Backend
from metatraderx.client import _level, _opt, _ts
from metatraderx.errors import BackendError, MTXError, NotConnected

Term = namedtuple("TerminalInfo", "company")
Acc = namedtuple("AccountInfo", "server")
RATES = np.dtype([("time", "<i8"), ("open", "<f8")])
OLD = datetime(2020, 1, 1, tzinfo=timezone.utc)
OLD2 = datetime(2020, 1, 2, tzinfo=timezone.utc)


class Rec(Backend):
    name = "rec"

    def __init__(self, fail=False, ret=1):
        self.calls, self.fail, self.ret, self.closed, self._alive = [], fail, ret, False, True

    @property
    def alive(self):
        return self._alive

    def call(self, m, a, k):
        self.calls.append((m, a, k))
        if self.fail and m not in ("terminal_info", "account_info"):
            raise BackendError("down")
        if m == "terminal_info":
            return Term("Acme")
        if m == "account_info":
            return Acc("Srv-1")
        if m == "last_error":
            return (1, "Success")
        if m.startswith("copy_"):
            return np.array([(1, 1.0)], dtype=RATES)
        return self.ret

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    monkeypatch.setenv("MTX_HOME", str(tmp_path / "h"))
    for k in ("MTX_TERMINAL", "MTX_URL", "MTX_CACHE", "MTX_OFFLINE", "MTX_VERBOSE", "MTX_CACHE_DIR", "MTX_CACHE_TTL"):
        monkeypatch.delenv(k, raising=False)


def conn(**kw):
    mt = MetaTrader(**kw)
    mt._backend = Rec()
    return mt


def test_helpers():
    assert [_level(v) for v in (True, False, "true", "off", "2", 3, -4, None, "x")] == [1, 0, 1, 0, 2, 3, 0, 0, 0]
    assert _opt(a=1, b=None) == {"a": 1}
    assert _ts(5) == 5.0 and _ts(datetime(1970, 1, 1, 0, 1)) == 60.0
    assert _ts(datetime(1970, 1, 1, 0, 1, tzinfo=timezone.utc)) == 60.0


def test_every_api_method_forwards():
    mt = conn()
    now = datetime.now(timezone.utc)
    skip = {"initialize", "login", "shutdown", "last_error", "version"}
    calls = {
        "account_info": (), "terminal_info": (), "symbols_total": (), "symbols_get": ("*",), "symbol_info": ("X",),
        "symbol_info_tick": ("X",), "symbol_select": ("X",), "market_book_add": ("X",), "market_book_get": ("X",),
        "market_book_release": ("X",), "copy_rates_from": ("X", 1, now, 5), "copy_rates_from_pos": ("X", 1, 0, 5),
        "copy_rates_range": ("X", 1, now, now), "copy_ticks_from": ("X", now, 5), "copy_ticks_range": ("X", now, now),
        "orders_total": (), "orders_get": (), "order_calc_margin": (0, "X", 1.0, 1.0),
        "order_calc_profit": (0, "X", 1.0, 1.0, 2.0), "order_check": ({},), "order_send": ({},), "positions_total": (),
        "positions_get": (), "history_orders_total": (now, now), "history_orders_get": (now, now),
        "history_deals_total": (now, now), "history_deals_get": (now, now),
    }
    assert set(calls) == set(API) - skip
    for name, args in calls.items():
        getattr(mt, name)(*args)
        assert mt._backend.calls[-1][0] == name
    mt.history_deals_get(ticket=5)
    assert mt._backend.calls[-1][1] == () and mt._backend.calls[-1][2] == {"ticket": 5}
    mt.positions_get(symbol="X", group="g")
    assert mt._backend.calls[-1][2] == {"symbol": "X", "group": "g"}


def test_version_and_last_error():
    mt = conn()
    assert mt.version() == 1
    assert mt.last_error() == (1, "Success")
    mt._err = (9, "x")
    assert mt.last_error() == (9, "x")
    mt._err = None
    mt._backend.fail = True
    assert mt.last_error()[0] == C.RES_E_INTERNAL_FAIL
    assert MetaTrader().last_error() == (C.RES_S_OK, "Success")


def test_not_connected_modes():
    mt = MetaTrader()
    assert mt.symbols_total() is None and mt.last_error()[0] == C.RES_E_INTERNAL_FAIL_INIT
    with pytest.raises(NotConnected):
        MetaTrader(strict=True).symbols_total()


def test_backend_failure_modes():
    mt = conn()
    mt._backend.fail = True
    assert mt.symbols_total() is None and "down" in mt.last_error()[1]
    st = conn(strict=True)
    st._backend.fail = True
    with pytest.raises(BackendError):
        st.symbols_total()


def test_read_only():
    mt = conn(read_only=True)
    assert mt.order_send({}) is None and mt.last_error()[0] == C.RES_E_UNSUPPORTED
    assert mt.order_check({}) is None
    assert mt.symbols_total() == 1
    assert not any(c[0].startswith("order_") for c in mt._backend.calls)


def test_connected_property_and_shutdown():
    mt = MetaTrader()
    assert not mt.connected and mt.backend_name is None
    mt._backend = Rec()
    assert mt.connected and mt.backend_name == "rec"
    be = mt._backend
    mt.shutdown()
    assert be.closed and mt._backend is None and be.calls[-1][0] == "shutdown"
    mt.shutdown()
    mt._backend = Rec()
    mt._backend.remote = True
    r = mt._backend
    mt.shutdown()
    assert [c[0] for c in r.calls] == []
    mt._backend = Rec(fail=True)
    mt.shutdown()


def test_context_manager(monkeypatch):
    mt = MetaTrader()
    monkeypatch.setattr(MetaTrader, "initialize", lambda self, *a, **k: True)
    with mt as m:
        assert m is mt
    monkeypatch.setattr(MetaTrader, "initialize", lambda self, *a, **k: False)
    with pytest.raises(MTXError):
        with MetaTrader():
            pass


def test_constructor_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("MTX_VERBOSE", "2")
    monkeypatch.setenv("MTX_OFFLINE", "yes")
    mt = MetaTrader()
    assert mt.offline and mt.verbose == 2 and mt.cache_info()["enabled"]
    mt2 = MetaTrader(offline=False, verbose=0, cache=False, cache_ttl=5)
    assert not mt2.offline and mt2._ttl == 5.0 and not mt2.cache_info()["enabled"]
    mt3 = MetaTrader(terminal="t.exe", version="4", prefix="p", login=1, password="x", server="s", timeout=3, portable=True)
    assert mt3.version_hint == 4 and mt3._terminal == "t.exe" and mt3._creds["login"] == 1


def test_cache_controls(tmp_path):
    mt = MetaTrader()
    assert mt.clear_cache() == 0 and mt.cache_info()["enabled"] is False
    mt.enable_cache(tmp_path / "c", ttl=10)
    assert mt.cache_info()["ttl"] == 10.0 and (tmp_path / "c").is_dir()
    mt._backend = Rec()
    mt.symbols_total()
    assert mt.cache_info()["entries"]["symbols_total"]["count"] == 1
    assert mt.clear_cache("symbols_total") == 1
    mt.disable_cache()
    assert mt._cache is None


def test_cache_env_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("MTX_CACHE", "1")
    monkeypatch.setenv("MTX_CACHE_DIR", str(tmp_path / "envc"))
    monkeypatch.setenv("MTX_CACHE_TTL", "7")
    mt = MetaTrader()
    assert mt.cache_info()["enabled"] and mt._ttl == 7.0 and (tmp_path / "envc").is_dir()


def test_cacheable_rules(tmp_path):
    mt = MetaTrader(cache=True, cache_dir=tmp_path)
    fresh = datetime.now(timezone.utc)
    assert mt._cacheable("symbols_get", (), {})
    assert not mt._cacheable("symbol_info_tick", ("X",), {})
    assert not mt._cacheable("orders_get", (), {})
    assert mt._cacheable("copy_rates_range", ("X", C.TIMEFRAME_H1, OLD, OLD2), {})
    assert not mt._cacheable("copy_rates_range", ("X", C.TIMEFRAME_H1, OLD, fresh), {})
    assert mt._cacheable("copy_rates_range", ("X",), {"timeframe": C.TIMEFRAME_H1, "date_to": OLD2}) is True
    assert mt._cacheable("copy_rates_from", ("X", C.TIMEFRAME_M1, OLD, 5), {})
    assert not mt._cacheable("copy_rates_from", ("X", C.TIMEFRAME_M1, fresh, 5), {})
    assert mt._cacheable("copy_ticks_range", ("X", OLD, OLD2), {})
    assert not mt._cacheable("copy_ticks_range", ("X", OLD, fresh), {})
    assert mt._cacheable("copy_ticks_from", ("X", OLD, 5), {})
    assert not mt._cacheable("copy_ticks_from", ("X", fresh - timedelta(seconds=5), 5), {})
    assert not mt._cacheable("copy_rates_from", ("X",), {})
    assert not MetaTrader()._cacheable("symbols_get", (), {})


def test_cache_ttl_for_static(tmp_path):
    mt = MetaTrader(cache=True, cache_dir=tmp_path, cache_ttl=60)
    mt._backend = Rec()
    mt.symbols_total()
    mt.symbols_total()
    assert [c[0] for c in mt._backend.calls].count("symbols_total") == 1
    mt._cache._db.execute("UPDATE c SET ts = ts - 1000")
    mt._cache._db.commit()
    mt.symbols_total()
    assert [c[0] for c in mt._backend.calls].count("symbols_total") == 2


def test_stale_cache_served_on_failure(tmp_path):
    mt = MetaTrader(cache=True, cache_dir=tmp_path)
    mt._backend = Rec(ret=42)
    assert mt.symbols_total() == 42
    mt._cache._db.execute("UPDATE c SET ts = ts - 100000")
    mt._cache._db.commit()
    mt._backend.fail = True
    assert mt.symbols_total() == 42


def test_none_results_not_cached(tmp_path):
    mt = MetaTrader(cache=True, cache_dir=tmp_path)
    mt._backend = Rec(ret=None)
    assert mt.symbols_total() is None
    assert mt.cache_info()["entries"] == {}


def test_scope_separates_servers(tmp_path):
    mt = MetaTrader(cache=True, cache_dir=tmp_path)
    mt._backend = Rec(ret=1)
    mt._detect_scope()
    assert mt._scope == "Acme|Srv-1"
    mt.symbols_total()
    mt._scope = "Other|Srv-2"
    mt._backend.ret = 2
    assert mt.symbols_total() == 2


def test_offline_flow(tmp_path, capsys):
    online = MetaTrader(cache=True, cache_dir=tmp_path)
    online._backend = Rec(ret=7)
    online._detect_scope()
    online.symbols_total()
    online.copy_rates_range("X", C.TIMEFRAME_H1, OLD, OLD2)
    online._cache.close()
    off = MetaTrader(offline=True, cache_dir=tmp_path, verbose=2)
    assert off.initialize() is True
    assert off._scope == "Acme|Srv-1"
    assert off.symbols_total() == 7
    assert off.copy_rates_range("X", C.TIMEFRAME_H1, OLD, OLD2)[0]["open"] == 1.0
    assert off.copy_rates_range("X", C.TIMEFRAME_H1, OLD, datetime(2020, 1, 5, tzinfo=timezone.utc)) is None
    assert off.last_error()[0] == C.RES_E_NOT_FOUND
    assert off.orders_total() is None
    assert off.login(1) is True
    off.shutdown()
    err = capsys.readouterr().err
    assert "answered from cache" in err and "not in the cache" in err and "unavailable offline" in err
    assert "login(1)" in err and "shutdown()" in err


def test_offline_quiet_by_default(tmp_path, capsys):
    off = MetaTrader(offline=True, cache_dir=tmp_path)
    off.initialize()
    off.symbols_total()
    off.shutdown()
    assert capsys.readouterr().err == ""


def test_pick_branches(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "IS_WIN", False)
    mt = MetaTrader(url="mtx://h:1")
    assert mt._pick(None) == ("remote", None, None)
    exe = tmp_path / "terminal64.exe"
    exe.write_bytes(b"")
    assert MetaTrader(terminal=str(exe), url="mtx://h")._pick(None)[0] == "local"
    assert MetaTrader()._pick(str(exe))[1] == str(exe)
    monkeypatch.setenv("MTX_URL", "mtx://z:1")
    assert MetaTrader()._pick(None)[0] == "remote"
    monkeypatch.delenv("MTX_URL")
    monkeypatch.setenv("MTX_TERMINAL", str(exe))
    monkeypatch.setenv("MTX_VERSION", "5")
    assert MetaTrader()._pick(None) == ("local", str(exe), 5)
    monkeypatch.delenv("MTX_TERMINAL")
    monkeypatch.setattr("metatraderx.client.find_terminals", lambda: [{"path": "a4", "version": 4}, {"path": "a5", "version": 5}])
    monkeypatch.delenv("MTX_VERSION")
    assert MetaTrader()._pick(None) == ("local", "a4", 4)
    assert MetaTrader(version=5)._pick(None) == ("local", "a5", 5)
    monkeypatch.setattr("metatraderx.client.find_terminals", lambda: [])
    from metatraderx.errors import TerminalNotFound

    with pytest.raises(TerminalNotFound):
        MetaTrader()._pick(None)
    monkeypatch.setattr(config, "IS_WIN", True)
    assert MetaTrader()._pick(None) == ("local", None, 5)


def test_make_backend_kinds(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "IS_WIN", False)
    from metatraderx.backends.mt4 import MT4Backend
    from metatraderx.backends.remote import RemoteBackend
    from metatraderx.backends.wine import WineBackend

    assert isinstance(MetaTrader(url="mtx://h")._make("remote", None, None), RemoteBackend)
    assert isinstance(MetaTrader()._make("local", "t", 4), MT4Backend)
    assert isinstance(MetaTrader(prefix="p")._make("local", "t", 5), WineBackend)


def test_initialize_remote_flow(tmp_path):
    from metatraderx.server import MTXServer

    host = MetaTrader(strict=True)
    host._backend = Rec(ret=True)
    srv = MTXServer(host, "127.0.0.1", 0, allow_login=True).start()
    try:
        mt = MetaTrader(url=f"mtx://127.0.0.1:{srv.port}", cache=True, cache_dir=tmp_path)
        assert mt.initialize(login=1, password="p") is True
        assert mt.backend_name == "remote" and mt._scope == "Acme|Srv-1"
        assert mt.login(2, "x") is True
        assert mt.symbols_total() is True
        mt.shutdown()
    finally:
        srv.stop()
    dead = MetaTrader(url="mtx://127.0.0.1:1")
    assert dead.initialize() is False
    with pytest.raises(BackendError):
        MetaTrader(url="mtx://127.0.0.1:1", strict=True).initialize()


def test_initialize_reuses_and_replaces_backend(monkeypatch):
    mt = MetaTrader(url="mtx://127.0.0.1:1")
    old = Rec()
    mt._backend = old
    assert mt.initialize() is False
    assert old.closed


def test_login_sets_scope():
    mt = conn()
    assert mt.login(1, "p", "S", 5) is True
    assert mt._backend.calls[0][0] == "login" and mt._backend.calls[0][2] == {"password": "p", "server": "S", "timeout": 5}
    mt._backend.ret = False
    assert mt.login(1) is False


def test_to_frame_staticmethod():
    arr = np.array([(1700000000, 1.0)], dtype=RATES)
    assert len(MetaTrader.to_frame(arr)) == 1
    assert len(mtx.to_frame(arr)) == 1


def test_symbol_names_edges():
    class Sym:
        def __init__(self, n):
            self.name = n

    mt = conn()
    mt._backend.ret = tuple(Sym(n) for n in "abc")
    assert mt.symbol_names(group="*") == ["a", "b", "c"]
    assert mt.symbol_names(first=0) == []
    assert mt.symbol_names(last=0) == []
    assert mt.symbol_names(last=2) == ["b", "c"]
    mt._backend.ret = None
    assert mt.symbol_names() is None


def test_module_level_functions(monkeypatch):
    fake = conn()
    old = mtx.default()
    try:
        assert mtx.set_default(fake) is fake and mtx.default() is fake
        assert mtx.symbols_total() == 1
        assert mtx.symbols_total.__doc__ == MetaTrader.symbols_total.__doc__
        assert mtx.symbols_total.__name__ == "symbols_total"
        got = mtx.configure(offline=True)
        assert got.offline and mtx.default() is got
        assert mtx.MetaTraderX is MetaTrader
        assert {"initialize", "copy_rates_range", "to_frame", "symbol_names"} <= set(mtx.__all__)
    finally:
        mtx.set_default(old)


def test_constants_exported():
    assert mtx.TIMEFRAME_H1 == C.TIMEFRAME_H1 and mtx.ORDER_TYPE_BUY == 0
    assert all(getattr(mtx, n) == v for n, v in C._export().items())


def test_types_records():
    from metatraderx.types import RECORDS

    assert {"AccountInfo", "SymbolInfo", "Tick", "TradePosition", "TradeDeal", "TradeOrder", "OrderSendResult"} <= set(RECORDS)
    assert RECORDS["Tick"]._fields[0] == "time"
