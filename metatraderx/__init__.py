"""MetaTraderX: `import metatraderx as mt5` works like `import MetaTrader5 as mt5` on Windows, Linux and macOS."""

from __future__ import annotations

from typing import Any

from ._version import __version__
from .backends.base import API
from .client import MetaTrader
from .constants import *  # noqa: F403
from .constants import _export
from .errors import (
    AuthError,
    BackendError,
    MTXError,
    NotConnected,
    RemoteError,
    SetupError,
    SetupWarning,
    TerminalNotFound,
)
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
    TradeRequest,
)
from .util import to_frame
from .wineenv import setup_problems

MetaTraderX = MetaTrader

_default = MetaTrader()  # MTX_OFFLINE=1 makes this instance offline


def default() -> MetaTrader:
    """The instance behind the module-level functions."""
    return _default


def set_default(instance: MetaTrader) -> MetaTrader:
    """Make an existing instance the one behind the module-level functions and return it."""
    global _default
    _default = instance
    return instance


def configure(**kwargs: Any) -> MetaTrader:
    """Replace the default instance, e.g. configure(url="mtx://host:8765", token="...", cache=True) or configure(offline=True, verbose=1)."""
    return set_default(MetaTrader(**kwargs))


def _bind(name: str) -> Any:
    def fn(*args: Any, **kwargs: Any) -> Any:
        return getattr(_default, name)(*args, **kwargs)

    fn.__name__ = name
    fn.__doc__ = getattr(MetaTrader, name).__doc__
    return fn


EXTRAS = ("symbol_names", "to_frame")

for _n in (*API, "symbol_names"):
    globals()[_n] = _bind(_n)

__all__ = sorted(
    [
        "__version__", "MetaTrader", "MetaTraderX", "default", "set_default", "configure", "to_frame", "symbol_names",
        "MTXError", "BackendError", "NotConnected", "TerminalNotFound", "SetupError", "SetupWarning", "RemoteError",
        "AuthError", "setup_problems",
        "AccountInfo", "BookInfo", "OrderCheckResult", "OrderSendResult", "SymbolInfo", "TerminalInfo", "Tick",
        "TradeDeal", "TradeOrder", "TradePosition", "TradeRequest", *API, *_export(),
    ]
)  # fmt: skip
