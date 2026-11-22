from __future__ import annotations
import json
import os
from collections import namedtuple

import numpy as np
import pytest

from metatraderx import cli, config, discovery, installer

Acc = namedtuple("AccountInfo", "login server name")
Sym = namedtuple("SymbolInfo", "name digits")
RATES = np.dtype([("time", "<i8"), ("open", "<f8")])


class FakeMT:
    inits: list = []
    ok = True
    names: list | None = ["EURUSD", "GBPUSD", "XAUUSD"]
    calls: list = []
    backend_name = "fake"

    def __init__(self, **kw):
        self.kw = kw

    def initialize(self, **kw):
        FakeMT.inits.append(kw)
        return FakeMT.ok

    def last_error(self):
        return (-10003, "boom")

    def shutdown(self):
        pass

    def account_info(self):
        return Acc(1, "Srv", "Me")

    def terminal_info(self):
        return {"name": "MT"}

    def version(self):
        return (5, 6328, "x")

    def symbol_names(self, group=None, first=None, last=None):
        n = FakeMT.names
        if n is None:
            return None
        return n[:first] if first is not None else n[-last:] if last else n

    def symbols_get(self, group=None):
        return tuple(Sym(n, 5) for n in FakeMT.names)

    def symbol_select(self, s, e=True):
        return s != "BAD"

    def symbol_info(self, s):
        return Sym(s, 5)

    def _rec(self, name, *a, **k):
        FakeMT.calls.append((name, a, k))
        return np.array([(1700000000, 1.5)], dtype=RATES)

    def copy_rates_range(self, *a, **k):
        return self._rec("copy_rates_range", *a)

    def copy_rates_from(self, *a, **k):
        return self._rec("copy_rates_from", *a)

    def copy_rates_from_pos(self, *a, **k):
        return self._rec("copy_rates_from_pos", *a)

    def copy_ticks_range(self, *a, **k):
        return self._rec("copy_ticks_range", *a)

    def copy_ticks_from(self, *a, **k):
        return self._rec("copy_ticks_from", *a)

    def history_deals_get(self, *a, **k):
        return self._rec("history_deals_get", *a, **k)

    def history_orders_get(self, *a, **k):
        return self._rec("history_orders_get", *a, **k)

    def cache_info(self):
        return {"path": "p", "entries": {"copy_rates": {"count": 2, "bytes": 1}}}

    def clear_cache(self, method=None):
        return 2


@pytest.fixture
def mt(monkeypatch, tmp_path):
    monkeypatch.setenv("MTX_HOME", str(tmp_path / "home"))
    for k in ("MTX_TERMINAL", "MTX_URL", "MTX_CACHE", "MTX_OFFLINE"):
        monkeypatch.delenv(k, raising=False)
    FakeMT.inits, FakeMT.calls, FakeMT.ok, FakeMT.names = [], [], True, ["EURUSD", "GBPUSD", "XAUUSD"]
    monkeypatch.setattr(cli, "MetaTrader", FakeMT)
    return FakeMT


def run(*argv):
    return cli.main(list(argv))


def test_main_error_paths(mt, capsys):
    mt.ok = False
    assert run("info", "account") == 1
    assert "could not connect" in capsys.readouterr().err
    assert run("fetch", "rates", "X", "--tf", "ZZ") == 1
    assert run("terminal", "select") == 1


def test_info(mt, capsys):
    assert run("info", "account") == 0
    assert '"login": 1' in capsys.readouterr().out
    assert run("info", "terminal", "--format", "csv") == 0
    assert run("info", "version") == 0
    assert capsys.readouterr().out.strip().endswith("5.6328")


def test_symbols(mt, capsys, tmp_path):
    assert run("symbols", "--first", "2") == 0
    assert capsys.readouterr().out == "EURUSD\nGBPUSD\n"
    assert run("symbols", "--format", "csv") == 0
    assert capsys.readouterr().out.startswith("name\nEURUSD")
    assert run("symbols", "--format", "json", "--last", "1") == 0
    assert json.loads(capsys.readouterr().out) == ["XAUUSD"]
    assert run("symbols", "--format", "jsonl") == 0
    assert capsys.readouterr().out.count("\n") == 3
    out = tmp_path / "s.csv"
    assert run("symbols", "-o", str(out)) == 0
    assert out.read_text().startswith("name")
    assert run("symbols", "--first", "1", "--last", "1") == 1
    assert run("symbols", "--full", "--first", "1") == 0
    assert run("symbols", "--full", "--last", "1") == 0
    assert run("symbols", "--full", "--last", "0", "--group", "*") == 0
    mt.names = None
    assert run("symbols") == 1


def test_symbol(mt, capsys):
    assert run("symbol", "EURUSD") == 0
    assert "EURUSD" in capsys.readouterr().out
    assert run("symbol", "BAD") == 1


def test_fetch_variants(mt, capsys, tmp_path):
    assert run("fetch", "rates", "EURUSD", "--tf", "M5", "--from", "2024-01-01", "--to", "2024-01-02") == 0
    assert mt.calls[-1][0] == "copy_rates_range"
    assert run("fetch", "rates", "EURUSD", "--from", "2024-01-01", "--count", "5") == 0
    assert mt.calls[-1][0] == "copy_rates_from"
    assert run("fetch", "rates", "EURUSD", "--pos", "3") == 0
    assert mt.calls[-1][0] == "copy_rates_from_pos"
    assert run("fetch", "ticks", "EURUSD", "--from", "2024-01-01", "--to", "2024-01-02", "--flags", "trade") == 0
    assert mt.calls[-1][0] == "copy_ticks_range"
    assert run("fetch", "ticks", "EURUSD", "--from", "2024-01-01") == 0
    assert mt.calls[-1][0] == "copy_ticks_from"
    assert run("fetch", "ticks", "EURUSD") == 1
    assert run("fetch", "deals", "--from", "-30d", "--group", "*USD*") == 0
    assert mt.calls[-1][2] == {"group": "*USD*"}
    assert run("fetch", "orders") == 0
    assert mt.calls[-1][0] == "history_orders_get"
    out = tmp_path / "r.csv"
    assert run("fetch", "rates", "EURUSD", "-o", str(out), "--raw-time") == 0
    assert "1700000000" in out.read_text()
    capsys.readouterr()


def test_config_command(mt, capsys):
    assert run("config") == 0
    assert "file:" in capsys.readouterr().out
    assert run("config", "bogus") == 1
    assert run("config", "token", "secret") == 0
    assert run("config", "token") == 0
    assert capsys.readouterr().out.strip().endswith("secret")
    assert run("config") == 0
    out = capsys.readouterr().out
    assert "***" in out and "secret" not in out
    assert run("config", "token", "") == 0
    assert "token" not in config.load()


def test_terminal_command(mt, capsys, tmp_path, monkeypatch):
    exe = tmp_path / "terminal64.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(discovery, "find_terminals", lambda *a, **k: [{"path": str(exe), "version": 5, "prefix": None}])
    assert run("terminal", "list") == 0
    assert "MT5" in capsys.readouterr().out
    assert run("terminal", "select", "0") == 0
    assert config.load()["terminal"] == str(exe)
    assert run("terminal", "list") == 0
    assert "*" in capsys.readouterr().out
    assert run("terminal", "show") == 0
    assert str(exe) in capsys.readouterr().out
    assert run("terminal", "select", "9") == 1
    assert run("terminal", "select", str(tmp_path / "none.exe")) == 1
    assert run("terminal", "select", str(exe)) == 0
    assert run("terminal", "clear") == 0
    assert "terminal" not in config.load()
    assert run("terminal", "show") == 0
    assert "none selected" in capsys.readouterr().out
    monkeypatch.setattr(discovery, "find_terminals", lambda *a, **k: [])
    assert run("terminal", "list") == 0
    assert "no terminals found" in capsys.readouterr().out


def test_login(mt, capsys, monkeypatch):
    assert run("login", "--login", "1", "--password", "p", "--server", "S") == 0
    assert "logged in" in capsys.readouterr().out
    monkeypatch.setattr("getpass.getpass", lambda *_: "pw")
    assert run("login", "--login", "1", "--server", "S") == 0
    assert mt.inits[-1]["password"] == "pw"
    mt.ok = False
    assert run("login", "--login", "1", "--password", "p", "--server", "S") == 1


def test_cache_command(mt, capsys, monkeypatch):
    assert run("cache", "info") == 0
    assert '"entries"' in capsys.readouterr().out
    assert run("cache", "clear", "-y") == 0
    assert "removed 2" in capsys.readouterr().out
    monkeypatch.setattr(installer, "ask", lambda *a, **k: False)
    assert run("cache", "clear", "--method", "copy_rates") == 1
    assert "nothing was removed" in capsys.readouterr().err


def test_install_download_setup_dispatch(mt, monkeypatch, capsys, tmp_path):
    seen = {}
    monkeypatch.setattr(installer, "install", lambda *a: seen.setdefault("install", a))
    monkeypatch.setattr(installer, "download", lambda *a: "/x/setup.exe")
    assert run("install", "4", "-y", "--method", "wine") == 0
    assert seen["install"][0] == 4
    assert run("download", "--os", "linux") == 0
    assert "/x/setup.exe" in capsys.readouterr().out
    monkeypatch.setattr(config, "IS_WIN", False)
    monkeypatch.setattr(installer, "setup_wine_python", lambda pre, yes: tmp_path / "python.exe")
    monkeypatch.setattr(discovery, "find_terminals", lambda *a, **k: [])
    assert run("setup", "-y") == 0
    assert "ready:" in capsys.readouterr().out
    assert run("setup", "--prefix", str(tmp_path), "-y") == 0


def test_setup_on_windows(mt, monkeypatch, capsys):
    monkeypatch.setattr(config, "IS_WIN", True)
    monkeypatch.setitem(__import__("sys").modules, "MetaTrader5", object())
    assert run("setup") == 0
    assert "ready" in capsys.readouterr().out


def test_doctor(mt, monkeypatch, capsys):
    monkeypatch.setattr(config, "IS_WIN", False)
    assert run("doctor") == 0
    out = capsys.readouterr().out
    assert "metatraderx" in out and "setup" in out and "xpra" in out


def test_serve_and_mt4_dispatch(mt, monkeypatch, capsys, tmp_path):
    class Srv:
        url = "mtx://127.0.0.1:1"

        def __init__(self, *a):
            self.a = a

        def serve_forever(self):
            raise KeyboardInterrupt

        def stop(self):
            Srv.stopped = True

    monkeypatch.setattr("metatraderx.server.MTXServer", Srv)
    assert run("serve", "--auth", "auto", "--read-only") == 0
    out = capsys.readouterr().out
    assert "token:" in out and "serving" in out and Srv.stopped
    monkeypatch.setattr("metatraderx.backends.mt4.install_bridge", lambda t: [tmp_path / "a.mq4"])
    assert run("mt4", "install-bridge") == 1
    config.save({"terminal": "t"})
    assert run("mt4", "install-bridge") == 0
    assert "copied" in capsys.readouterr().out


def test_display_dispatch(mt, monkeypatch, capsys):
    monkeypatch.setattr("metatraderx.display.setup_display", lambda y, t: {"xpra": "/bin/xpra", "cloudflared": None})
    assert run("display", "setup", "-y") == 0
    out = capsys.readouterr().out
    assert "missing" in out and out.strip().endswith("ready")
    monkeypatch.setattr("metatraderx.display.serve_display", lambda *a: 0)
    assert run("display") == 1
    config.save({"terminal": "t"})
    assert run("display") == 0


def test_winedebug_option(monkeypatch):
    monkeypatch.delenv("MTX_WINEDEBUG", raising=False)
    monkeypatch.setattr(installer, "install", lambda *a: None)
    assert cli.main(["--winedebug", "fixme", "install", "-y"]) == 0
    assert os.environ["MTX_WINEDEBUG"] == "fixme"
    monkeypatch.delenv("MTX_WINEDEBUG")


def test_serve_binds_next_free_port(monkeypatch):
    import argparse

    tried = []

    class Srv:
        def __init__(self, mt, host, port, *a):
            tried.append(port)
            if port < 8767:
                raise OSError(98, "Address already in use")
            self.port = port

    monkeypatch.setattr("metatraderx.server.MTXServer", Srv)
    ns = argparse.Namespace(host="127.0.0.1", port=None, read_only=False, allow_login=False, cert=None, key=None)
    assert cli._bind(ns, None, None).port == 8767 and tried == [8765, 8766, 8767]
    ns.port = 8000
    with pytest.raises(cli.CLIError, match="unavailable"):
        cli._bind(ns, None, None)
