from __future__ import annotations

import pytest

from metatraderx import MetaTrader, config, wineenv
from metatraderx.errors import SetupError, SetupWarning, TerminalNotFound


@pytest.fixture
def posix(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "IS_WIN", False)
    monkeypatch.setenv("MTX_HOME", str(tmp_path / "home"))
    for k in ("MTX_WINE", "MTX_WINE_PYTHON", "MTX_WINEPREFIX", "MTX_OFFLINE", "MTX_CACHE", "MTX_URL", "MTX_TERMINAL"):
        monkeypatch.delenv(k, raising=False)
    return tmp_path


def _terminal(root, with_python=False):
    pre = root / "pre"
    exe = pre / "drive_c" / "Program Files" / "MT5" / "terminal64.exe"
    (exe.parent / "MQL5").mkdir(parents=True)
    exe.write_bytes(b"")
    if with_python:
        py = pre / "drive_c" / "Python312" / "python.exe"
        py.parent.mkdir(parents=True)
        py.write_bytes(b"")
    return pre, exe


def test_problems_empty_on_windows(monkeypatch):
    monkeypatch.setattr(config, "IS_WIN", True)
    assert wineenv.setup_problems() == []


def test_problems_wine_missing(posix, monkeypatch):
    pre, exe = _terminal(posix, True)
    monkeypatch.setattr(wineenv, "wine_bin", lambda: None)
    assert wineenv.setup_problems(exe) == ["Wine is not installed"]
    assert wineenv.setup_problems(python=False) == ["Wine is not installed"]


def test_problems_python_missing(posix, monkeypatch):
    pre, exe = _terminal(posix)
    monkeypatch.setattr(wineenv, "wine_bin", lambda: "/usr/bin/wine")
    out = wineenv.setup_problems(exe)
    assert len(out) == 1 and "Windows Python" in out[0] and str(pre) in out[0]
    assert wineenv.setup_problems(exe, python=False) == []


def test_problems_not_in_prefix(posix, monkeypatch):
    exe = posix / "elsewhere" / "terminal64.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"")
    monkeypatch.setattr(wineenv, "wine_bin", lambda: "/usr/bin/wine")
    monkeypatch.setenv("HOME", str(posix / "nohome"))
    assert "Wine prefix" in wineenv.setup_problems(exe)[0]


def test_problems_ready(posix, monkeypatch):
    pre, exe = _terminal(posix, True)
    monkeypatch.setattr(wineenv, "wine_bin", lambda: "/usr/bin/wine")
    assert wineenv.setup_problems(exe) == []
    assert wineenv.setup_problems(prefix=pre) == []


def test_initialize_reports_setup(posix, monkeypatch):
    _, exe = _terminal(posix, True)
    monkeypatch.setattr(wineenv, "wine_bin", lambda: None)
    mt = MetaTrader(terminal=exe)
    with pytest.warns(SetupWarning, match="mtx setup"):
        assert mt.initialize() is False
    code, msg = mt.last_error()
    assert code < 0 and "not set up" in msg and "Wine is not installed" in msg
    assert mt.symbols_total() is None and not mt.connected


def test_initialize_strict_raises(posix, monkeypatch):
    _, exe = _terminal(posix, True)
    monkeypatch.setattr(wineenv, "wine_bin", lambda: None)
    with pytest.raises(SetupError, match="not set up"):
        MetaTrader(terminal=exe, strict=True).initialize()


def test_context_manager_raises(posix, monkeypatch):
    _, exe = _terminal(posix, True)
    monkeypatch.setattr(wineenv, "wine_bin", lambda: None)
    with pytest.warns(SetupWarning), pytest.raises(Exception, match="not set up"):
        with MetaTrader(terminal=exe):
            pass


def test_no_terminal_and_no_wine_is_a_setup_problem(posix, monkeypatch):
    monkeypatch.setattr(wineenv, "wine_bin", lambda: None)
    monkeypatch.setattr("metatraderx.client.find_terminals", lambda: [])
    with pytest.raises(SetupError, match="Wine is not installed"):
        MetaTrader(strict=True).initialize()


def test_no_terminal_with_wine_stays_not_found(posix, monkeypatch):
    monkeypatch.setattr(wineenv, "wine_bin", lambda: "/usr/bin/wine")
    monkeypatch.setattr("metatraderx.client.find_terminals", lambda: [])
    with pytest.raises(TerminalNotFound):
        MetaTrader(strict=True).initialize()


def test_no_silent_offline_fallback(posix, monkeypatch):
    _, exe = _terminal(posix, True)
    monkeypatch.setattr(wineenv, "wine_bin", lambda: None)
    mt = MetaTrader(terminal=exe, cache=True)
    with pytest.warns(SetupWarning):
        assert mt.initialize() is False
    assert mt.offline is False


def test_offline_needs_no_setup(posix, monkeypatch, recwarn):
    monkeypatch.setattr(wineenv, "wine_bin", lambda: None)
    mt = MetaTrader(offline=True)
    assert mt.initialize() is True
    assert not [w for w in recwarn if issubclass(w.category, SetupWarning)]


def test_mt4_needs_only_wine(posix, monkeypatch):
    pre = posix / "pre"
    exe = pre / "drive_c" / "MT4" / "terminal.exe"
    (exe.parent / "MQL4").mkdir(parents=True)
    exe.write_bytes(b"")
    monkeypatch.setattr(wineenv, "wine_bin", lambda: "/usr/bin/wine")
    assert wineenv.setup_problems(exe, python=False) == []
    monkeypatch.setattr(wineenv, "wine_bin", lambda: None)
    mt = MetaTrader(terminal=exe, version=4)
    with pytest.warns(SetupWarning):
        assert mt.initialize() is False


def test_public_names():
    import metatraderx

    assert metatraderx.setup_problems is wineenv.setup_problems
    assert issubclass(metatraderx.SetupWarning, UserWarning)
