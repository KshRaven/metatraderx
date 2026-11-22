"""Exceptions raised by MetaTraderX."""

from __future__ import annotations

__all__ = [
    "MTXError",
    "BackendError",
    "NotConnected",
    "TerminalNotFound",
    "SetupError",
    "RemoteError",
    "AuthError",
    "SetupWarning",
]


class MTXError(Exception):
    """Base error for MetaTraderX."""


class BackendError(MTXError):
    """The backend could not be started or stopped answering."""


class NotConnected(MTXError):
    """No terminal connection exists; call initialize() first."""


class TerminalNotFound(MTXError):
    """No MetaTrader terminal executable could be located."""


class SetupError(MTXError):
    """A required component (Wine, Windows Python, MetaTrader5 package) is missing or failed to install."""


class RemoteError(MTXError):
    """The remote MetaTraderX server returned an error."""


class AuthError(RemoteError):
    """The remote MetaTraderX server rejected the token."""


class SetupWarning(UserWarning):
    """Issued by initialize() when it returns False because `mtx setup` has not been run on this system."""
