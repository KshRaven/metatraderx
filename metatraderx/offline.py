"""`import metatraderx.offline as mt5`: the same API answered only from the local cache, no terminal or server needed.

Set MTX_VERBOSE=1 (or call configure(verbose=1)) to see a notice from initialize, login and shutdown; 2 also reports every call.
"""

from __future__ import annotations

from typing import Any

from . import __all__ as _all
from . import to_frame  # noqa: F401
from .backends.base import API
from .client import MetaTrader
from .constants import *  # noqa: F403
from .errors import *  # noqa: F403
from .types import *  # noqa: F403

_default = MetaTrader(offline=True)


def default() -> MetaTrader:
    """The offline instance behind the module-level functions."""
    return _default


def configure(**kwargs: Any) -> MetaTrader:
    """Replace the offline instance, e.g. configure(verbose=1, cache_dir="...")."""
    global _default
    kwargs["offline"] = True
    _default = MetaTrader(**kwargs)
    return _default


def _call(name: str) -> Any:
    def fn(*args: Any, **kwargs: Any) -> Any:
        return getattr(_default, name)(*args, **kwargs)

    fn.__name__ = name
    fn.__doc__ = getattr(MetaTrader, name).__doc__
    return fn


for _n in (*API, "symbol_names"):
    globals()[_n] = _call(_n)

__all__ = [n for n in _all if n not in ("set_default", "MetaTraderX")]
