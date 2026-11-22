"""The Backend interface and the list of API function names."""

from __future__ import annotations

from typing import Any

__all__ = ["Backend", "API", "TRADING"]

API = (
    "initialize", "login", "shutdown", "version", "last_error", "account_info", "terminal_info", "symbols_total",
    "symbols_get", "symbol_info", "symbol_info_tick", "symbol_select", "market_book_add", "market_book_get",
    "market_book_release", "copy_rates_from", "copy_rates_from_pos", "copy_rates_range", "copy_ticks_from",
    "copy_ticks_range", "orders_total", "orders_get", "order_calc_margin", "order_calc_profit", "order_check",
    "order_send", "positions_total", "positions_get", "history_orders_total", "history_orders_get",
    "history_deals_total", "history_deals_get",
)  # fmt: skip

TRADING = ("order_send", "order_check")


class Backend:
    """Transport to a terminal: call(method, args, kwargs) returns what the MetaTrader5 package would."""

    name = "base"
    remote = False

    def call(self, method: str, args: tuple, kwargs: dict) -> Any:
        """Run one MetaTrader5 API function in the terminal and return its result.

        Args:
            method: A name from API, for example "copy_rates_range".
            args: Positional arguments of the function.
            kwargs: Keyword arguments of the function.

        Raises:
            BackendError: The transport failed or the call is not supported.
        """
        raise NotImplementedError

    @property
    def alive(self) -> bool:
        """True while the connection to the terminal or server is usable."""
        return True

    def close(self) -> None:
        """Release the connection and anything started for it."""
