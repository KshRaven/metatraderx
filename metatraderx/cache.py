"""Optional SQLite cache for symbol data, rates, ticks and deal history. Disabled unless switched on."""

from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from . import codec
from .types import RECORDS

__all__ = ["Cache", "make_key"]


def make_key(scope: str, method: str, args: tuple, kwargs: dict) -> str:
    """Stable cache key for one call: a hash of the scope (company and server), method, arguments and keywords."""
    raw = repr((scope, method, args, sorted(kwargs.items())))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


class Cache:
    """SQLite store of API results, one row per call, safe to share between threads."""

    def __init__(self, directory: str | Path, name: str = "mtx") -> None:
        """Open (and create when needed) `<directory>/<name>.sqlite3`."""
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"{name}.sqlite3"
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS c (k TEXT PRIMARY KEY, m TEXT NOT NULL, ts REAL NOT NULL, d BLOB NOT NULL)"
        )
        self._db.commit()

    def get(self, key: str, max_age: float | None = None) -> tuple[Any, float] | None:
        """Return (value, stored time) for a key, or None when missing or older than max_age seconds."""
        with self._lock:
            row = self._db.execute("SELECT ts, d FROM c WHERE k=?", (key,)).fetchone()
        if row is None:
            return None
        ts, blob = row
        if max_age is not None and time.time() - ts > max_age:
            return None
        return codec.unpack(blob, RECORDS), ts

    def put(self, key: str, method: str, value: Any) -> None:
        """Store a value under a key, replacing an older one; method is kept so entries can be cleared per method."""
        blob = codec.pack(value)
        with self._lock:
            self._db.execute("REPLACE INTO c (k, m, ts, d) VALUES (?, ?, ?, ?)", (key, method, time.time(), blob))
            self._db.commit()

    def clear(self, method: str | None = None) -> int:
        """Delete the entries of one method, or all when method is None. Returns how many were removed."""
        with self._lock:
            cur = (
                self._db.execute("DELETE FROM c WHERE m=?", (method,))
                if method
                else self._db.execute("DELETE FROM c")
            )
            self._db.commit()
            return cur.rowcount

    def stats(self) -> dict:
        """The file path and, per method, the number of entries and their size in bytes."""
        with self._lock:
            rows = self._db.execute("SELECT m, COUNT(*), SUM(LENGTH(d)) FROM c GROUP BY m").fetchall()
        return {
            "path": str(self.path),
            "entries": {m: {"count": c, "bytes": b or 0} for m, c, b in rows},
        }

    def close(self) -> None:
        """Close the database."""
        with self._lock:
            self._db.close()
