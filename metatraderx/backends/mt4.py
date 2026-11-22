"""MetaTrader 4 backend: reads data through the bundled MetaTraderXBridge expert (experimental)."""

from __future__ import annotations

import fnmatch
import json
import os
import shutil
import socket
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .. import config, wineenv
from .. import constants as C
from ..discovery import prefix_of
from ..errors import BackendError, SetupError
from ..types import AccountInfo, SymbolInfo, TerminalInfo, Tick, TradeDeal, TradePosition
from .base import Backend

__all__ = ["MT4Backend", "install_bridge", "RATES_DTYPE"]

BRIDGE = Path(__file__).resolve().parent.parent / "mql" / "MetaTraderXBridge.mq4"
RATES_DTYPE = np.dtype(
    [("time", "<i8"), ("open", "<f8"), ("high", "<f8"), ("low", "<f8"), ("close", "<f8"),
     ("tick_volume", "<u8"), ("spread", "<i4"), ("real_volume", "<u8")]
)  # fmt: skip
_TF = {
    C.TIMEFRAME_M1: 1, C.TIMEFRAME_M5: 5, C.TIMEFRAME_M15: 15, C.TIMEFRAME_M30: 30, C.TIMEFRAME_H1: 60,
    C.TIMEFRAME_H4: 240, C.TIMEFRAME_D1: 1440, C.TIMEFRAME_W1: 10080, C.TIMEFRAME_MN1: 43200,
}  # fmt: skip


def _ts(d: Any) -> int:
    if isinstance(d, datetime):
        return int(d.replace(tzinfo=d.tzinfo or timezone.utc).timestamp())
    return int(d)


def _rec(cls: Any, d: dict) -> Any:
    return cls(*[d.get(f) for f in cls._fields])


def _rates(rows: Any) -> Any:
    if not rows:
        return None
    return np.array([tuple(r) for r in rows], dtype=RATES_DTYPE)


class MT4Backend(Backend):
    """MetaTrader 4 has no Python API; data is read through the bundled MetaTraderXBridge expert (experimental)."""

    name = "mt4"

    def __init__(self, port: int | None = None) -> None:
        """Prepare the bridge listener.

        Args:
            port: Loopback port the expert connects to. Defaults to MTX_MT4_PORT or 5555.
        """
        self.port = int(port or config.setting("mt4_port", 5555))
        self._listener: socket.socket | None = None
        self._conn: socket.socket | None = None
        self._buf = b""
        self._id = 0
        self._lock = threading.RLock()
        self._proc: subprocess.Popen | None = None
        self._error = (1, "Success")

    @property
    def alive(self) -> bool:
        """True while the bridge expert is connected."""
        return self._conn is not None

    def start(self, path: str | None, timeout: float = 60.0) -> None:
        """Listen for the bridge expert, launching the terminal first when a path is given and it is not connected.

        Raises:
            BackendError: The expert did not connect within timeout seconds.
            SetupError: Wine is needed but missing (Linux and macOS).
        """
        with self._lock:
            if self._listener is None:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", self.port))
                s.listen(1)
                self._listener = s
            if path and self._proc is None and not self._bridge_up(0.5):
                self._launch(path)
            if not self._bridge_up(timeout):
                raise BackendError(
                    f"the MetaTraderXBridge expert did not connect on 127.0.0.1:{self.port}; "
                    "run: mtx mt4 install-bridge, compile it in MetaEditor, attach it to a chart with Allow DLL imports enabled"
                )

    def _launch(self, path: str) -> None:
        if config.IS_WIN:
            self._proc = subprocess.Popen([path], cwd=str(Path(path).parent))
            return
        wine = wineenv.wine_bin()
        if not wine:
            raise SetupError("wine was not found; run: mtx setup")
        env = wineenv.base_env(prefix_of(path))
        extra, _ = wineenv.ensure_display()
        env.update(extra)
        self._proc = subprocess.Popen([wine, path], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _bridge_up(self, timeout: float) -> bool:
        if self._conn is not None:
            return True
        self._listener.settimeout(timeout)
        try:
            self._conn, _ = self._listener.accept()
        except (socket.timeout, OSError):
            return False
        self._conn.settimeout(30)
        self._buf = b""
        return True

    def _rpc(self, m: str, *a: Any) -> Any:
        with self._lock:
            if self._conn is None and not self._bridge_up(5):
                raise BackendError("the MetaTraderXBridge expert is not connected")
            self._id += 1
            line = "|".join([str(self._id), m, *map(str, a)]) + "\n"
            try:
                self._conn.sendall(line.encode("utf-8"))
                while b"\n" not in self._buf:
                    chunk = self._conn.recv(1 << 20)
                    if not chunk:
                        raise ConnectionError("closed")
                    self._buf += chunk
            except (OSError, ConnectionError) as e:
                self._conn = None
                raise BackendError(f"the MetaTraderXBridge connection dropped: {e}") from e
            raw, _, self._buf = self._buf.partition(b"\n")
        resp = json.loads(raw.decode("utf-8", "replace"))
        if not resp.get("ok"):
            raise BackendError(str(resp.get("e")))
        return resp.get("r")

    def call(self, method: str, args: tuple, kwargs: dict) -> Any:
        """Run an API function through the bridge.

        Raises:
            BackendError: The function is not supported for MetaTrader 4, or the bridge failed.
        """
        h = getattr(self, "_m_" + method, None)
        if h is None:
            raise BackendError(f"{method} is not supported for MetaTrader 4")
        return h(*args, **kwargs)

    def _m_initialize(self, path: str | None = None, **kw: Any) -> bool:
        self.start(path, float(kw.get("timeout") or 60))
        return True

    def _m_login(self, *a: Any, **k: Any) -> bool:
        raise BackendError("login is not supported for MetaTrader 4; log in inside the terminal")

    def _m_shutdown(self) -> None:
        with self._lock:
            for s in (self._conn, self._listener):
                if s:
                    s.close()
            self._conn = self._listener = None
            if self._proc:
                self._proc.terminate()
                self._proc = None

    def _m_version(self) -> tuple:
        t = self._rpc("terminal_info")
        return (4, int(t.get("build") or 0), "")

    def _m_last_error(self) -> tuple:
        return self._error

    def _m_account_info(self) -> Any:
        return _rec(AccountInfo, self._rpc("account_info"))

    def _m_terminal_info(self) -> Any:
        return _rec(TerminalInfo, self._rpc("terminal_info"))

    def _m_symbols_total(self) -> int:
        return len(self._rpc("symbols", 0))

    def _m_symbols_get(self, group: str | None = None) -> tuple:
        rows = [_rec(SymbolInfo, d) for d in self._rpc("symbols", 0)]
        if group:
            pats = [g.strip() for g in group.split(",") if g.strip()]
            inc = [p for p in pats if not p.startswith("!")]
            exc = [p[1:] for p in pats if p.startswith("!")]
            rows = [
                r for r in rows
                if (not inc or any(fnmatch.fnmatch(r.name, p) for p in inc)) and not any(fnmatch.fnmatch(r.name, p) for p in exc)
            ]  # fmt: skip
        return tuple(rows)

    def _m_symbol_info(self, symbol: str) -> Any:
        d = self._rpc("symbol_info", symbol)
        return _rec(SymbolInfo, d) if d else None

    def _m_symbol_info_tick(self, symbol: str) -> Any:
        d = self._rpc("tick", symbol)
        return _rec(Tick, d) if d else None

    def _m_symbol_select(self, symbol: str, enable: bool = True) -> bool:
        return bool(self._rpc("symbol_select", symbol, 1 if enable else 0))

    def _m_copy_rates_from_pos(self, symbol: str, timeframe: int, start_pos: int, count: int) -> Any:
        return _rates(self._rpc("rates_pos", symbol, _TF[timeframe], start_pos, count))

    def _m_copy_rates_range(self, symbol: str, timeframe: int, date_from: Any, date_to: Any) -> Any:
        return _rates(self._rpc("rates_range", symbol, _TF[timeframe], _ts(date_from), _ts(date_to)))

    def _m_positions_get(self, *a: Any, **k: Any) -> Any:
        rows = [t for t in self._rpc("open_trades") if t["type"] in (0, 1)]
        if k.get("symbol"):
            rows = [t for t in rows if t["symbol"] == k["symbol"]]
        out = tuple(
            _rec(TradePosition, {
                "ticket": x["ticket"], "time": x["open_time"], "time_msc": x["open_time"] * 1000,
                "time_update": x["open_time"], "time_update_msc": x["open_time"] * 1000, "type": x["type"],
                "magic": x["magic"], "identifier": x["ticket"], "reason": 0, "volume": x["volume"],
                "price_open": x["open_price"], "sl": x["sl"], "tp": x["tp"], "price_current": x["close_price"],
                "swap": x["swap"], "profit": x["profit"], "symbol": x["symbol"], "comment": x["comment"],
                "external_id": "",
            })
            for x in rows
        )  # fmt: skip
        return out or None

    def _m_positions_total(self) -> int:
        return len(self._m_positions_get() or ())

    def _m_history_deals_get(self, date_from: Any = None, date_to: Any = None, **k: Any) -> Any:
        rows = self._rpc("history", _ts(date_from or 0), _ts(date_to or time.time()))
        if k.get("group"):
            rows = [t for t in rows if fnmatch.fnmatch(t["symbol"], k["group"])]
        out = tuple(
            _rec(TradeDeal, {
                "ticket": x["ticket"], "order": x["ticket"], "time": x["close_time"], "time_msc": x["close_time"] * 1000,
                "type": x["type"], "entry": 1, "magic": x["magic"], "position_id": x["ticket"], "reason": 0,
                "volume": x["volume"], "price": x["close_price"], "commission": x["commission"], "swap": x["swap"],
                "profit": x["profit"], "fee": 0.0, "symbol": x["symbol"], "comment": x["comment"], "external_id": "",
            })
            for x in rows if x["type"] in (0, 1)
        )  # fmt: skip
        return out or None

    def _m_history_deals_total(self, date_from: Any, date_to: Any) -> int:
        return len(self._m_history_deals_get(date_from, date_to) or ())

    def close(self) -> None:
        """Close the bridge connection and stop a terminal that was launched by this backend."""
        self._m_shutdown()


def install_bridge(terminal: str) -> list[Path]:
    """Copy the bridge expert into the terminal's MQL4/Experts folder(s). Returns the destinations."""
    exe = Path(terminal)
    dests: list[Path] = []
    if (exe.parent / "MQL4").is_dir():
        dests.append(exe.parent / "MQL4" / "Experts")
    pre = prefix_of(exe)
    roots = [Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal"]
    if pre:
        roots = list((pre / "drive_c" / "users").glob("*/AppData/Roaming/MetaQuotes/Terminal")) + list(
            (pre / "drive_c" / "users").glob("*/Application Data/MetaQuotes/Terminal")
        )
    elif config.IS_WIN:
        roots = [Path(os.environ.get("APPDATA", "")) / "MetaQuotes" / "Terminal"]
    for r in roots:
        for mql in r.glob("*/MQL4"):
            dests.append(mql / "Experts")
    out = []
    for d in dict.fromkeys(dests):
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BRIDGE, d / BRIDGE.name)
        out.append(d / BRIDGE.name)
    if not out:
        raise SetupError("no MQL4 data folder found; start the terminal once, then retry")
    return out


