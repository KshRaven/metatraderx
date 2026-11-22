"""Windows backend: the official MetaTrader5 package in this process."""

from __future__ import annotations

import threading
from typing import Any

from ..errors import SetupError
from .base import Backend

__all__ = ["NativeBackend"]


class NativeBackend(Backend):
    """Windows: drives the terminal through the official MetaTrader5 package in this process."""

    name = "native"

    def __init__(self) -> None:
        """Import the official package.

        Raises:
            SetupError: The MetaTrader5 package is not installed.
        """
        try:
            import MetaTrader5 as mt5
        except ImportError as e:
            raise SetupError("the MetaTrader5 package is missing; run: pip install MetaTrader5") from e
        self._mt5 = mt5
        self._lock = threading.RLock()

    def call(self, method: str, args: tuple, kwargs: dict) -> Any:
        """Call the function of the same name in the official MetaTrader5 package (one call at a time)."""
        fn = getattr(self._mt5, method)
        with self._lock:
            return fn(*args, **kwargs)
