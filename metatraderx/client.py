"""MetaTrader: the same API as the official MetaTrader5 package on every platform."""

from __future__ import annotations

import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import config, wineenv
from . import constants as C
from .backends.base import API, TRADING, Backend
from .backends.remote import RemoteBackend
from .cache import Cache, make_key
from .discovery import find_terminals, terminal_version
from .errors import BackendError, MTXError, NotConnected, SetupError, SetupWarning, TerminalNotFound
from .types import (
    AccountInfo,
    BookInfo,
    OrderCheckResult,
    OrderSendResult,
    SymbolInfo,
    TerminalInfo,
    Tick,
    TradeDeal,
    TradeOrder,
    TradePosition,
)
from .util import tf_seconds, to_frame

if TYPE_CHECKING:
    import numpy as np

__all__ = ["MetaTrader"]

_STATIC = {"symbols_total", "symbols_get", "symbol_info"}
_RANGED = {"copy_rates_from", "copy_rates_range", "copy_ticks_from", "copy_ticks_range"}


def _level(v: Any) -> int:
    """Verbosity from a bool, an int or text such as "true" or "2"."""
    if isinstance(v, str):
        t = v.strip().lower()
        if t in config._TRUE:
            return 1
        if t in config._FALSE:
            return 0
    try:
        return max(int(v), 0)
    except (TypeError, ValueError):
        return 0


def _ts(d: Any) -> float:
    if isinstance(d, datetime):
        return d.replace(tzinfo=d.tzinfo or timezone.utc).timestamp()
    return float(d)


class MetaTrader:
    """The same API as the official MetaTrader5 package, for one terminal or server, on Windows, Linux and macOS.

    Calls return what the official package returns: result records (namedtuples), numpy structured arrays, numbers, or
    None when a call fails. After a failure last_error() holds the reason. With strict=True problems raise
    MTXError subclasses instead.

    Example:
        >>> mt = MetaTrader(terminal=r"D:\\Brokers\\Acme\\terminal64.exe")
        >>> if mt.initialize():
        ...     print(mt.account_info())
        ...     mt.shutdown()

    The class is also a context manager (initialize on entry, shutdown on exit). `MetaTraderX` is an alias.
    See https://www.mql5.com/en/docs/python_metatrader5 for the meaning of every field and constant.
    """

    def __init__(
        self,
        terminal: str | Path | None = None,
        url: str | None = None,
        token: str | None = None,
        *,
        version: int | None = None,
        prefix: str | Path | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        timeout: int | None = None,
        portable: bool | None = None,
        cache: bool | None = None,
        cache_dir: str | Path | None = None,
        cache_ttl: float | None = None,
        offline: bool | None = None,
        verbose: bool | int | None = None,
        strict: bool = False,
        read_only: bool = False,
    ) -> None:
        """Create an instance; nothing is contacted until initialize() is called.

        Args:
            terminal: Path to the terminal executable, official or a broker build. Found automatically when omitted,
                or taken from `mtx terminal select` / MTX_TERMINAL.
            url: Address of a running `mtx serve` (mtx://host:port, https://domain/base) used instead of a local
                terminal. Taken from MTX_URL when neither terminal nor url is given.
            token: Token the server requires.
            version: 5 or 4. Detected from the terminal when omitted.
            prefix: Wine prefix holding the terminal (Linux and macOS). Derived from the terminal path when omitted.
            login: Default account number for initialize().
            password: Default account password for initialize().
            server: Default trade server name for initialize().
            timeout: Default connection timeout in milliseconds for initialize().
            portable: Default for starting the terminal in portable mode.
            cache: Store fetched data in an SQLite cache. Defaults to MTX_CACHE, off when unset.
            cache_dir: Folder of the cache. Defaults to MTX_CACHE_DIR or the mtx home folder.
            cache_ttl: Seconds a cached symbol list or specification stays fresh. Default 3600.
            offline: Answer only from the cache and never contact a terminal. Defaults to MTX_OFFLINE.
            verbose: False/0 silent, True/1 notices from initialize, login and shutdown while offline, 2 also
                every offline call. Text such as "true" or "2" is accepted. Defaults to MTX_VERBOSE.
            strict: Raise MTXError subclasses on infrastructure failures instead of returning None.
            read_only: Reject order_send and order_check on this instance.
        """
        self._terminal = str(terminal) if terminal else None
        self._url, self._token = url, token
        self.version_hint = int(version) if version else None
        self._prefix = str(prefix) if prefix else None
        self._creds = {"login": login, "password": password, "server": server, "timeout": timeout, "portable": portable}
        offline = config.env_bool(config.setting("offline"), False) if offline is None else offline
        self.offline = offline
        self.verbose = _level(config.setting("verbose", 0) if verbose is None else verbose)
        self.strict = strict
        self.read_only = read_only
        self._backend: Backend | None = None
        self._err: tuple | None = None
        self._scope = "default"
        self._cache: Cache | None = None
        self._ttl = 3600.0
        want = config.env_bool(config.setting("cache"), False) if cache is None else cache
        if want or offline:
            self.enable_cache(cache_dir, cache_ttl)
        elif cache_ttl is not None:
            self._ttl = float(cache_ttl)

    def _say(self, level: int, msg: str) -> None:
        if self.verbose >= level:
            print(f"[mtx] offline mode: {msg}", file=sys.stderr, flush=True)

    # -- cache ------------------------------------------------------------------------------------------------
    def enable_cache(self, directory: str | Path | None = None, ttl: float | None = None) -> None:
        """Turn the data cache on.

        Args:
            directory: Cache folder. Defaults to MTX_CACHE_DIR or `<mtx home>/cache`.
            ttl: Seconds a cached symbol list or specification stays fresh. Defaults to MTX_CACHE_TTL or 3600.
        """
        d = directory or config.setting("cache_dir") or config.home() / "cache"
        self._cache = Cache(d)
        t = ttl if ttl is not None else config.setting("cache_ttl")
        if t is not None:
            self._ttl = float(t)

    def disable_cache(self) -> None:
        """Turn the data cache off; the stored data stays on disk."""
        if self._cache:
            self._cache.close()
        self._cache = None

    def clear_cache(self, method: str | None = None) -> int:
        """Delete cached data without asking and return the number of entries removed.

        Args:
            method: Only entries of this API method, for example "copy_rates_range". All entries when omitted.
        """
        return self._cache.clear(method) if self._cache else 0

    def cache_info(self) -> dict:
        """Describe the cache: whether it is enabled, its ttl, scope, file path and entry counts per method."""
        return {"enabled": self._cache is not None, "ttl": self._ttl, "scope": self._scope, **(self._cache.stats() if self._cache else {})}

    # -- connection ---------------------------------------------------------------------------------------------
    def __enter__(self) -> MetaTrader:
        """Call initialize(); raise MTXError (after shutdown) when it fails."""
        if not self.initialize():
            err = self.last_error()
            self.shutdown()
            raise MTXError(f"initialize failed: {err}")
        return self

    def __exit__(self, *exc: Any) -> None:
        """Call shutdown()."""
        self.shutdown()

    @property
    def connected(self) -> bool:
        """True while a terminal or server connection is open."""
        return self._backend is not None and self._backend.alive

    @property
    def backend_name(self) -> str | None:
        """Transport in use: "native", "wine", "remote" or "mt4"; None when not connected."""
        return self._backend.name if self._backend else None

    def _fail(self, e: Exception, code: int = C.RES_E_INTERNAL_FAIL) -> None:
        self._err = (code, str(e))

    def _pick(self, path: str | None) -> tuple[str, str | None, int | None]:
        """Returns (mode, terminal path, version); mode is local or remote."""
        term = path or self._terminal
        url = None if term else self._url
        if not term and not url:
            term = config.setting("terminal")
            if not term:
                url = config.setting("url")
        if url:
            return "remote", None, None
        v = self.version_hint or (int(config.setting("version")) if config.setting("version") else None)
        if term:
            return "local", str(term), v or terminal_version(term) or 5
        if config.IS_WIN and (v or 5) == 5:
            return "local", None, 5
        found = find_terminals()
        if v:
            found = [t for t in found if t["version"] == v] or found
        if not found:
            raise TerminalNotFound("no MetaTrader terminal found; install one with `mtx install` or pass terminal=")
        return "local", found[0]["path"], v or found[0]["version"] or 5

    def _require_setup(self, term: str | None, ver: int | None) -> None:
        """Windows needs nothing; Linux and macOS need Wine, and for MetaTrader 5 its Windows Python, from `mtx setup`."""
        problems = wineenv.setup_problems(term, self._prefix or config.setting("wineprefix"), python=term is not None and ver != 4)
        if problems:
            raise SetupError(
                "metatraderx is not set up on this system: " + "; ".join(problems)
                + ". Run `mtx setup` once (or set MTX_WINEPREFIX for a terminal in a custom Wine prefix), then try again"
            )

    def _make(self, mode: str, term: str | None, ver: int | None) -> Backend:
        if mode == "remote":
            return RemoteBackend(self._url or config.setting("url"), self._token or config.setting("token"))
        if ver == 4:
            from .backends.mt4 import MT4Backend

            return MT4Backend()
        if config.IS_WIN:
            from .backends.native import NativeBackend

            return NativeBackend()
        from .backends.wine import WineBackend

        return WineBackend(prefix=self._prefix or config.setting("wineprefix"))

    def initialize(
        self,
        path: str | Path | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        timeout: int | None = None,
        portable: bool | None = None,
    ) -> bool:
        """Connect to the terminal (or server) and start it when needed.

        Without arguments the terminal given to the constructor, the one saved with `mtx terminal select`, or the
        server is used. On Linux and macOS this needs `mtx setup` to have been run; if not, False is returned with a
        SetupWarning (or SetupError when strict).

        Args:
            path: Terminal executable to use for this call.
            login: Account number. Falls back to the constructor value.
            password: Account password.
            server: Trade server name as shown in the terminal.
            timeout: Connection timeout in milliseconds.
            portable: Start the terminal in portable mode.

        Returns:
            True when connected (offline mode always succeeds), False otherwise; see last_error().
        """
        kw = {k: v for k, v in {"login": login, "password": password, "server": server, "timeout": timeout, "portable": portable}.items() if v is not None}
        for k, v in self._creds.items():
            if v is not None:
                kw.setdefault(k, v)
        self._err = None
        try:
            if self.offline:
                self._load_scope()
                self._say(1, f"initialize() uses cached data only (scope {self._scope!r}); no terminal is contacted")
                return True
            if self._backend is not None:
                self.shutdown()
            try:
                mode, term, ver = self._pick(str(path) if path else None)
            except TerminalNotFound:
                self._require_setup(None, self.version_hint)
                raise
            if mode == "local":
                self._require_setup(term, ver)
            be = self._make(mode, term, ver)
            self._backend = be
            if mode == "remote":
                if not be.ping():
                    raise BackendError("the MetaTraderX server did not answer")
                ok = bool(be.call("login", (), kw)) if {"login", "password"} <= kw.keys() else True
            else:
                if be.name == "wine":
                    be.start(term)
                if term:
                    kw["path"] = term
                ok = bool(be.call("initialize", (), kw))
            if ok:
                self._detect_scope()
            return ok
        except MTXError as e:
            if self.strict:
                raise
            self._fail(e, C.RES_E_INTERNAL_FAIL_INIT)
            if isinstance(e, SetupError):
                warnings.warn(str(e), SetupWarning, stacklevel=2)
            return False

    def login(self, login: int, password: str | None = None, server: str | None = None, timeout: int | None = None) -> bool:
        """Log the connected terminal into a trade account.

        Args:
            login: Account number.
            password: Account password. The terminal's saved password is used when omitted.
            server: Trade server name as shown in the terminal.
            timeout: Timeout in milliseconds.

        Returns:
            True when the account was accepted. A server must be started with `--allow-login` to permit this call.
        """
        if self.offline:
            self._load_scope()
            self._say(1, f"login({login}) accepted without contacting a server; cached data only")
            return True
        kw = {k: v for k, v in {"password": password, "server": server, "timeout": timeout}.items() if v is not None}
        r = self._c("login", (login,), kw)
        if r:
            self._detect_scope()
        return bool(r)

    def shutdown(self) -> None:
        """Close the connection and stop what mtx started for it (the Wine worker, the MetaTrader 4 listener)."""
        be, self._backend = self._backend, None
        if be is None:
            if self.offline:
                self._say(1, "shutdown()")
            return
        try:
            if not be.remote and be.name != "mt4":
                be.call("shutdown", (), {})
        except MTXError:
            pass
        finally:
            be.close()

    def last_error(self) -> tuple:
        """The result of the last call as (code, description); (1, "Success") when it worked. Codes are the RES_* constants."""
        if self._err is not None:
            return self._err
        if self._backend is not None:
            try:
                return tuple(self._backend.call("last_error", (), {}))
            except MTXError as e:
                return (C.RES_E_INTERNAL_FAIL, str(e))
        return (C.RES_S_OK, "Success")

    def version(self) -> tuple | None:
        """Terminal version as (version, build, release date text), or None on failure."""
        return self._c("version", (), {})

    # -- extras (not part of the MetaTrader5 package) ---------------------------------------------------------------
    @staticmethod
    def to_frame(data: Any, time_unit: str = "s") -> Any:
        """Convert rates, ticks or a sequence of result records to a pandas DataFrame (needs pandas).

        Args:
            data: Array from copy_rates_* / copy_ticks_*, or a tuple of records such as positions_get().
            time_unit: Unit of the integer `time` column, "s" by default.

        Returns:
            A DataFrame; `time` (and `time_msc`) become UTC datetimes. Empty when data is None.
        """
        return to_frame(data, time_unit)

    def symbol_names(self, group: str | None = None, first: int | None = None, last: int | None = None) -> list[str] | None:
        """Symbol names only, e.g. ["EURUSD", "XAUUSD"].

        Args:
            group: Filter such as "*USD*,!*EUR*" (see symbols_get).
            first: Keep only this many names from the start.
            last: Keep only this many names from the end.
        """
        res = self.symbols_get(group=group) if group else self.symbols_get()
        if res is None:
            return None
        names = [s.name for s in res]
        if first is not None:
            names = names[: max(first, 0)]
        elif last is not None:
            names = names[-last:] if last > 0 else []
        return names

    # -- cache scope ----------------------------------------------------------------------------------------------
    def _detect_scope(self) -> None:
        try:
            t = self._backend.call("terminal_info", (), {})
            a = self._backend.call("account_info", (), {})
            self._scope = f"{getattr(t, 'company', '')}|{getattr(a, 'server', '')}" if (t or a) else "default"
            if self._cache and self._scope != "default":
                self._cache.put("__scope__", "meta", self._scope)
        except MTXError:
            pass

    def _load_scope(self) -> None:
        if self._cache:
            hit = self._cache.get("__scope__")
            if hit:
                self._scope = hit[0]

    # -- dispatch --------------------------------------------------------------------------------------------------
    def _cacheable(self, name: str, args: tuple, kw: dict) -> bool:
        if self._cache is None:
            return False
        if name in _STATIC:
            return True
        if name not in _RANGED:
            return False
        now = time.time()
        try:
            if name == "copy_rates_range":
                return _ts(args[3] if len(args) > 3 else kw["date_to"]) < now - 2 * tf_seconds(args[1] if len(args) > 1 else kw["timeframe"])
            if name == "copy_rates_from":
                return _ts(args[2] if len(args) > 2 else kw["date_from"]) < now - 2 * tf_seconds(args[1] if len(args) > 1 else kw["timeframe"])
            if name == "copy_ticks_range":
                return _ts(args[2] if len(args) > 2 else kw["date_to"]) < now - 120
            return _ts(args[1] if len(args) > 1 else kw["date_from"]) < now - 120
        except (KeyError, TypeError, ValueError):
            return False

    def _c(self, name: str, args: tuple = (), kw: dict | None = None) -> Any:
        kw = kw or {}
        key = None
        if self._cacheable(name, args, kw):
            key = make_key(self._scope, name, args, kw)
            hit = self._cache.get(key, None if self.offline else (self._ttl if name in _STATIC else None))
            if hit is not None:
                if self.offline:
                    self._say(2, f"{name}() answered from cache")
                return hit[0]
        if self.offline:
            self._say(2, f"{name}() is not in the cache" if key is not None else f"{name}() is unavailable offline")
            self._err = (C.RES_E_NOT_FOUND, "offline: not in cache")
            return None
        if self._backend is None:
            e = NotConnected("not connected; call initialize() first")
            if self.strict:
                raise e
            self._fail(e, C.RES_E_INTERNAL_FAIL_INIT)
            return None
        if self.read_only and name in TRADING:
            self._err = (C.RES_E_UNSUPPORTED, "read-only")
            return None
        try:
            res = self._backend.call(name, args, kw)
        except MTXError as e:
            if key is not None:
                stale = self._cache.get(key)
                if stale is not None:
                    return stale[0]
            if self.strict:
                raise
            self._fail(e)
            return None
        self._err = None
        if key is not None and res is not None:
            self._cache.put(key, name, res)
        return res

    # -- MetaTrader5 API ---------------------------------------------------------------------------------------------
    def account_info(self) -> AccountInfo | None:
        """Information about the current trade account, or None on failure."""
        return self._c("account_info")

    def terminal_info(self) -> TerminalInfo | None:
        """Status and settings of the connected terminal, or None on failure."""
        return self._c("terminal_info")

    def symbols_total(self) -> int | None:
        """Number of symbols in the terminal, or None on failure."""
        return self._c("symbols_total")

    def symbols_get(self, group: str | None = None) -> tuple[SymbolInfo, ...] | None:
        """All symbols, or those matching a group filter.

        Args:
            group: Comma-separated name masks, with * as wildcard and a leading ! to exclude, for example
                "*USD*,!*EUR*". All symbols when omitted.

        Returns:
            A tuple of SymbolInfo, or None on failure.
        """
        return self._c("symbols_get", (), _opt(group=group))

    def symbol_info(self, symbol: str) -> SymbolInfo | None:
        """Full specification of a symbol, or None when it is unknown."""
        return self._c("symbol_info", (symbol,))

    def symbol_info_tick(self, symbol: str) -> Tick | None:
        """The last tick of a symbol, or None on failure."""
        return self._c("symbol_info_tick", (symbol,))

    def symbol_select(self, symbol: str, enable: bool = True) -> bool | None:
        """Show a symbol in Market Watch (enable=True) or hide it. A symbol must be shown before its data can be copied."""
        return self._c("symbol_select", (symbol, enable))

    def market_book_add(self, symbol: str) -> bool | None:
        """Subscribe to market depth (Depth of Market) updates for a symbol."""
        return self._c("market_book_add", (symbol,))

    def market_book_get(self, symbol: str) -> tuple[BookInfo, ...] | None:
        """Current market depth entries of a symbol; market_book_add must have been called first."""
        return self._c("market_book_get", (symbol,))

    def market_book_release(self, symbol: str) -> bool | None:
        """Cancel the market depth subscription of a symbol."""
        return self._c("market_book_release", (symbol,))

    def copy_rates_from(self, symbol: str, timeframe: int, date_from: datetime | int | float, count: int) -> np.ndarray | None:
        """Bars starting from a date and going back in time.

        Args:
            symbol: Symbol name.
            timeframe: A TIMEFRAME_* constant.
            date_from: Time of the first (latest) bar; a datetime (UTC when naive) or a Unix timestamp.
            count: Number of bars.

        Returns:
            A numpy structured array with time, open, high, low, close, tick_volume, spread and real_volume, or None.
        """
        return self._c("copy_rates_from", (symbol, timeframe, date_from, count))

    def copy_rates_from_pos(self, symbol: str, timeframe: int, start_pos: int, count: int) -> np.ndarray | None:
        """Bars counted from the current one: start_pos 0 is the bar being formed, 1 the previous one, and so on.

        Returns the same array layout as copy_rates_from, or None on failure.
        """
        return self._c("copy_rates_from_pos", (symbol, timeframe, start_pos, count))

    def copy_rates_range(self, symbol: str, timeframe: int, date_from: datetime | int | float, date_to: datetime | int | float) -> np.ndarray | None:
        """Bars between two dates (both inclusive; datetimes are UTC when naive).

        Returns the same array layout as copy_rates_from, or None on failure.
        """
        return self._c("copy_rates_range", (symbol, timeframe, date_from, date_to))

    def copy_ticks_from(self, symbol: str, date_from: datetime | int | float, count: int, flags: int = C.COPY_TICKS_ALL) -> np.ndarray | None:
        """Ticks starting from a date.

        Args:
            symbol: Symbol name.
            date_from: Start time; a datetime (UTC when naive) or a Unix timestamp.
            count: Number of ticks.
            flags: COPY_TICKS_ALL, COPY_TICKS_INFO (bid/ask changes) or COPY_TICKS_TRADE (last/volume changes).

        Returns:
            A numpy structured array with time, bid, ask, last, volume, time_msc, flags and volume_real, or None.
        """
        return self._c("copy_ticks_from", (symbol, date_from, count, flags))

    def copy_ticks_range(self, symbol: str, date_from: datetime | int | float, date_to: datetime | int | float, flags: int = C.COPY_TICKS_ALL) -> np.ndarray | None:
        """Ticks between two dates; same flags and array layout as copy_ticks_from."""
        return self._c("copy_ticks_range", (symbol, date_from, date_to, flags))

    def orders_total(self) -> int | None:
        """Number of active (pending) orders."""
        return self._c("orders_total")

    def orders_get(self, symbol: str | None = None, group: str | None = None, ticket: int | None = None) -> tuple[TradeOrder, ...] | None:
        """Active orders, optionally filtered by symbol, group mask or ticket. A tuple of TradeOrder, or None."""
        return self._c("orders_get", (), _opt(symbol=symbol, group=group, ticket=ticket))

    def order_calc_margin(self, action: int, symbol: str, volume: float, price: float) -> float | None:
        """Margin in the account currency needed for an ORDER_TYPE_BUY or ORDER_TYPE_SELL of the given volume and price."""
        return self._c("order_calc_margin", (action, symbol, volume, price))

    def order_calc_profit(self, action: int, symbol: str, volume: float, price_open: float, price_close: float) -> float | None:
        """Profit in the account currency of a trade opened at price_open and closed at price_close."""
        return self._c("order_calc_profit", (action, symbol, volume, price_open, price_close))

    def order_check(self, request: dict[str, Any]) -> OrderCheckResult | None:
        """Check whether a trade request could be executed, without sending it. Disabled on read-only instances and servers."""
        return self._c("order_check", (request,))

    def order_send(self, request: dict[str, Any]) -> OrderSendResult | None:
        """Send a trade request to the server. Disabled on read-only instances and servers.

        Args:
            request: Dict with the TradeRequest fields: action, symbol, volume, type, price, sl, tp, deviation,
                magic, comment, type_time, type_filling and so on.

        Returns:
            An OrderSendResult whose retcode is a TRADE_RETCODE_* constant, or None on failure.
        """
        return self._c("order_send", (request,))

    def positions_total(self) -> int | None:
        """Number of open positions."""
        return self._c("positions_total")

    def positions_get(self, symbol: str | None = None, group: str | None = None, ticket: int | None = None) -> tuple[TradePosition, ...] | None:
        """Open positions, optionally filtered by symbol, group mask or ticket. A tuple of TradePosition, or None."""
        return self._c("positions_get", (), _opt(symbol=symbol, group=group, ticket=ticket))

    def history_orders_total(self, date_from: datetime | int | float, date_to: datetime | int | float) -> int | None:
        """Number of historical orders between two dates."""
        return self._c("history_orders_total", (date_from, date_to))

    def history_orders_get(
        self,
        date_from: datetime | int | float | None = None,
        date_to: datetime | int | float | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple[TradeOrder, ...] | None:
        """Historical orders, selected by a date range (with an optional group mask), by ticket or by position id."""
        args = (date_from, date_to) if date_from is not None else ()
        return self._c("history_orders_get", args, _opt(group=group, ticket=ticket, position=position))

    def history_deals_total(self, date_from: datetime | int | float, date_to: datetime | int | float) -> int | None:
        """Number of historical deals between two dates."""
        return self._c("history_deals_total", (date_from, date_to))

    def history_deals_get(
        self,
        date_from: datetime | int | float | None = None,
        date_to: datetime | int | float | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple[TradeDeal, ...] | None:
        """Historical deals, selected by a date range (with an optional group mask), by ticket or by position id."""
        args = (date_from, date_to) if date_from is not None else ()
        return self._c("history_deals_get", args, _opt(group=group, ticket=ticket, position=position))


def _opt(**kw: Any) -> dict:
    return {k: v for k, v in kw.items() if v is not None}


assert set(API) <= set(dir(MetaTrader))
