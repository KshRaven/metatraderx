"""Wire format shared by the Wine worker, the MetaTraderX server and the clients.

A message is a JSON header followed by raw numpy buffers; nothing is pickled, so decoding untrusted input cannot
execute code. Standalone on purpose: the worker loads this file by path inside Windows Python.
"""

from __future__ import annotations

import json
import struct
from collections import namedtuple
from datetime import datetime
from typing import Any

import numpy as np

__all__ = ["pack", "unpack", "send_frame", "recv_frame", "MAX_FRAME"]

MAX_FRAME = 1 << 30
_dynamic: dict = {}


class _Enc:
    """Collects binary buffers while a value is encoded."""

    def __init__(self) -> None:
        self.bufs: list = []
        self.size = 0

    def add(self, b: bytes) -> int:
        off = self.size
        self.bufs.append(b)
        self.size += len(b)
        return off

    def enc(self, o: Any) -> Any:
        if o is None or isinstance(o, (bool, int, float, str)):
            return o
        if isinstance(o, np.generic):
            return self.enc(o.item())
        if isinstance(o, np.ndarray):
            a = np.ascontiguousarray(o)
            if a.dtype.hasobject:
                return [self.enc(x) for x in a.tolist()]
            d = a.dtype.descr if a.dtype.names else a.dtype.str
            raw = a.tobytes()
            return {"__nd__": d, "s": list(a.shape), "o": self.add(raw), "n": len(raw)}
        if isinstance(o, tuple) and (hasattr(o, "_fields") or hasattr(o, "_asdict")):
            names = list(o._fields) if hasattr(o, "_fields") else list(o._asdict())
            return {"__rec__": type(o).__name__, "f": names, "v": [self.enc(x) for x in o]}
        if isinstance(o, tuple):
            return {"__t__": [self.enc(x) for x in o]}
        if isinstance(o, (list, set, frozenset)):
            return [self.enc(x) for x in o]
        if isinstance(o, dict):
            if all(isinstance(k, str) for k in o):
                return {k: self.enc(v) for k, v in o.items()}
            return {"__d__": [[self.enc(k), self.enc(v)] for k, v in o.items()]}
        if isinstance(o, datetime):
            return {"__dt__": o.isoformat()}
        if isinstance(o, (bytes, bytearray, memoryview)):
            return {"__b__": self.add(bytes(o)), "n": len(o)}
        if hasattr(o, "_asdict"):
            return self.enc(o._asdict())
        raise TypeError(f"cannot encode {type(o).__name__}")


def pack(obj: Any) -> bytes:
    """Encode a value (numbers, text, lists, dicts, tuples, datetimes, numpy arrays, named tuples) to bytes."""
    e = _Enc()
    head = json.dumps(e.enc(obj), separators=(",", ":")).encode("utf-8")
    return struct.pack("<I", len(head)) + head + b"".join(e.bufs)


def _field(f: Any) -> tuple:
    name, fmt = f[0], f[1]
    fmt = fmt if isinstance(fmt, str) else [_field(x) for x in fmt]
    return (name, fmt) if len(f) == 2 else (name, fmt, tuple(f[2]))


def _dtype(d: Any) -> np.dtype:
    return np.dtype(d) if isinstance(d, str) else np.dtype([_field(f) for f in d])


def _rec(name: str, fields: list, records: dict | None) -> Any:
    cls = (records or {}).get(name)
    if cls is None or tuple(cls._fields) != tuple(fields):
        key = (name, tuple(fields))
        cls = _dynamic.get(key)
        if cls is None:
            cls = _dynamic[key] = namedtuple(name, fields)
    return cls


def unpack(data: bytes, records: dict | None = None) -> Any:
    """Decode bytes made by pack. records maps record names to named tuple classes (see types.RECORDS)."""
    mv = memoryview(data)
    (hl,) = struct.unpack_from("<I", mv, 0)
    base = 4 + hl
    head = json.loads(bytes(mv[4:base]))

    def dec(o: Any) -> Any:
        if isinstance(o, list):
            return [dec(x) for x in o]
        if not isinstance(o, dict):
            return o
        if "__nd__" in o:
            dt = _dtype(o["__nd__"])
            n = o["n"]
            if n == 0:
                return np.empty(tuple(o["s"]), dtype=dt)
            return np.frombuffer(mv[base + o["o"] : base + o["o"] + n], dtype=dt).reshape(o["s"]).copy()
        if "__rec__" in o:
            return _rec(o["__rec__"], o["f"], records)(*[dec(x) for x in o["v"]])
        if "__t__" in o:
            return tuple(dec(x) for x in o["__t__"])
        if "__dt__" in o:
            return datetime.fromisoformat(o["__dt__"])
        if "__b__" in o:
            return bytes(mv[base + o["__b__"] : base + o["__b__"] + o["n"]])
        if "__d__" in o:
            return {_hashable(dec(k)): dec(v) for k, v in o["__d__"]}
        return {k: dec(v) for k, v in o.items()}

    return dec(head)


def _hashable(k: Any) -> Any:
    return tuple(k) if isinstance(k, list) else k


def send_frame(sock: Any, payload: bytes) -> None:
    """Send a length-prefixed message on a socket."""
    sock.sendall(struct.pack("<Q", len(payload)) + payload)


def _recv_exact(sock: Any, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(n - len(buf), 1 << 20))
        if not chunk:
            raise ConnectionError("connection closed")
        buf += chunk
    return bytes(buf)


def recv_frame(sock: Any) -> bytes:
    """Receive one length-prefixed message; ConnectionError when the peer closes or the message is too large."""
    (n,) = struct.unpack("<Q", _recv_exact(sock, 8))
    if n > MAX_FRAME:
        raise ConnectionError("frame too large")
    return _recv_exact(sock, n)
