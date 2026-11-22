"""Turn MetaTrader results into rows and write them as CSV, JSON or JSON lines."""

from __future__ import annotations

import csv
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["to_rows", "write_rows", "parse_dt", "parse_tf"]

_TIME = ("time", "time_setup", "time_done", "time_expiration", "time_update")


def _iso(v: Any, ms: bool) -> Any:
    if not isinstance(v, (int, float)) or v <= 0:
        return v
    return datetime.fromtimestamp(v / (1000 if ms else 1), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def to_rows(data: Any, raw_time: bool = False) -> list[dict]:
    """Turn arrays, result records or lists of them into a list of dicts; time fields become ISO 8601 unless raw_time."""
    if data is None:
        return []
    if hasattr(data, "dtype") and data.dtype.names:
        rows = [dict(zip(data.dtype.names, r)) for r in data.tolist()]
    elif hasattr(data, "_asdict"):
        rows = [data._asdict()]
    elif isinstance(data, (list, tuple)):
        rows = [d._asdict() if hasattr(d, "_asdict") else dict(d) if isinstance(d, dict) else {"value": d} for d in data]
    elif isinstance(data, dict):
        rows = [data]
    else:
        rows = [{"value": data}]
    if not raw_time:
        for r in rows:
            for k in list(r):
                if k in _TIME:
                    r[k] = _iso(r[k], False)
                elif k.endswith("_msc"):
                    r[k] = _iso(r[k], True)
    return rows


def parse_dt(text: str) -> datetime:
    """'now', '-7d', '-12h', '2024-01-31' or '2024-01-31T10:30' (UTC)."""
    t = text.strip().lower()
    now = datetime.now(timezone.utc)
    if t == "now":
        return now
    if t[:1] == "-" and t[-1:] in "smhdw" and t[1:-1].isdigit():
        from datetime import timedelta

        unit = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}[t[-1]]
        return now - timedelta(**{unit: int(t[1:-1])})
    d = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def parse_tf(name: str) -> int:
    """Timeframe constant from its short name such as "M15" or "h1"; ValueError when unknown."""
    from . import constants as C

    v = getattr(C, "TIMEFRAME_" + name.upper(), None)
    if v is None:
        raise ValueError(f"unknown timeframe {name!r}")
    return v


def write_rows(rows: list[dict], out: str | None, fmt: str | None = None) -> None:
    """Write rows as csv, json or jsonl to a file (format from fmt or the extension) or to stdout when out is None or "-"."""
    fmt = (fmt or (Path(out).suffix.lstrip(".").lower() if out else "json")) or "json"
    if fmt not in ("csv", "json", "jsonl"):
        raise ValueError("format must be csv, json or jsonl")
    buf = io.StringIO()
    if fmt == "csv":
        cols = list(rows[0]) if rows else []
        w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    elif fmt == "jsonl":
        buf.write("".join(json.dumps(r, default=str) + "\n" for r in rows))
    else:
        json.dump(rows, buf, indent=2, default=str)
        buf.write("\n")
    if out and out != "-":
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(buf.getvalue(), encoding="utf-8", newline="")
        print(f"{len(rows)} rows -> {out}", file=sys.stderr)
    else:
        sys.stdout.write(buf.getvalue())
