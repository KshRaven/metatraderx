"""Small helpers: timeframe lengths and DataFrame conversion."""

from __future__ import annotations

from typing import Any

__all__ = ["to_frame", "tf_seconds"]


def tf_seconds(tf: int) -> int:
    """Length in seconds of a MetaTrader 5 timeframe constant."""
    if tf < 0x4000:
        return tf * 60
    grp, n = tf & 0xC000, tf & 0x3FFF
    if grp == 0x4000:
        return n * 3600
    if grp == 0x8000:
        return n * 7 * 86400
    return n * 30 * 86400


def to_frame(data: Any, time_unit: str = "s") -> Any:
    """Convert a rates/ticks structured array (or a tuple of records) to a pandas DataFrame with a datetime index."""
    import pandas as pd

    if data is None:
        return pd.DataFrame()
    if hasattr(data, "dtype") and data.dtype.names:
        df = pd.DataFrame(data)
    elif data and hasattr(data[0], "_asdict"):
        df = pd.DataFrame([d._asdict() for d in data])
    else:
        df = pd.DataFrame(list(data))
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], unit=time_unit, utc=True)
    if "time_msc" in df.columns:
        df["time_msc"] = pd.to_datetime(df["time_msc"], unit="ms", utc=True)
    return df
