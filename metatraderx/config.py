"""Settings: environment variable (MTX_<NAME>) first, then the saved config file, then the default."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

__all__ = ["home", "config_file", "load", "save", "setting", "env_bool", "IS_WIN", "IS_MAC", "IS_LINUX"]

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

_TRUE = {"1", "true", "yes", "on", "y"}
_FALSE = {"0", "false", "no", "off", "n", ""}


def home(create: bool = True) -> Path:
    """Directory for configuration, downloads and the default Wine prefix."""
    if os.environ.get("MTX_HOME"):
        p = Path(os.environ["MTX_HOME"])
    elif IS_WIN:
        p = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "metatraderx"
    elif IS_MAC:
        p = Path.home() / "Library" / "Application Support" / "metatraderx"
    else:
        p = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "metatraderx"
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def config_file() -> Path:
    """Path of the saved settings file (config.json in home())."""
    return home(create=False) / "config.json"


def load() -> dict:
    """The saved settings, or an empty dict when there are none."""
    try:
        return json.loads(config_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(data: dict) -> None:
    """Write the saved settings."""
    home()
    config_file().write_text(json.dumps(data, indent=2), encoding="utf-8")


def env_bool(value: Any, default: bool = False) -> bool:
    """Read a setting as a boolean: 1/true/yes/on/y and 0/false/no/off/n/empty; default for anything else or None."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    return default


def setting(name: str, default: Any = None) -> Any:
    """A setting by name: MTX_<NAME> from the environment, else the saved value, else default."""
    v = os.environ.get("MTX_" + name.upper())
    if v is not None:
        return v
    v = load().get(name.lower())
    return default if v is None else v
