"""Backend that talks to a running `mtx serve` over HTTP(S)."""

from __future__ import annotations

import http.client
import threading
from typing import Any
from urllib.parse import urlparse

from .. import codec
from ..errors import AuthError, BackendError, RemoteError
from ..types import RECORDS
from .base import Backend

__all__ = ["RemoteBackend", "parse_url"]


def parse_url(url: str) -> tuple[bool, str, int, str]:
    """Split a server address into (tls, host, port, base path).

    mtx:// and a bare host:port mean plain HTTP on port 8765 by default; https:// and mtxs:// mean TLS on port 443.
    """
    u = url.strip()
    if "://" not in u:
        u = "mtx://" + u
    pu = urlparse(u)
    tls = pu.scheme in ("https", "mtxs")
    host = pu.hostname or "127.0.0.1"
    port = pu.port or (443 if tls else 8765)
    return tls, host, port, pu.path.rstrip("/")


class RemoteBackend(Backend):
    """Talks to a running `mtx serve` over HTTP(S); works through reverse proxies and domains."""

    name = "remote"
    remote = True

    def __init__(self, url: str, token: str | None = None, timeout: float = 60.0) -> None:
        """Prepare a client for the server at url; nothing is sent until the first call.

        Args:
            url: mtx://host:port, https://domain/base or host:port.
            token: Token for the Authorization header.
            timeout: Seconds to wait for each request.
        """
        self.tls, self.host, self.port, self.base = parse_url(url)
        self.token = token
        self.timeout = timeout
        self._conn: http.client.HTTPConnection | None = None
        self._lock = threading.RLock()

    def _connect(self) -> http.client.HTTPConnection:
        cls = http.client.HTTPSConnection if self.tls else http.client.HTTPConnection
        return cls(self.host, self.port, timeout=self.timeout)

    def _post(self, body: bytes) -> bytes:
        headers = {"Content-Type": "application/x-mtx", "Content-Length": str(len(body))}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        last: Exception | None = None
        for _ in range(2):
            try:
                if self._conn is None:
                    self._conn = self._connect()
                self._conn.request("POST", self.base + "/rpc", body=body, headers=headers)
                r = self._conn.getresponse()
                data = r.read()
                if r.status == 401:
                    raise AuthError("the server rejected the token")
                if r.status != 200:
                    raise RemoteError(f"server returned HTTP {r.status}: {data[:200].decode('utf-8', 'replace')}")
                return data
            except (OSError, http.client.HTTPException) as e:
                last = e
                try:
                    if self._conn:
                        self._conn.close()
                finally:
                    self._conn = None
        raise BackendError(f"cannot reach {self.host}:{self.port}: {last}")

    def call(self, method: str, args: tuple, kwargs: dict) -> Any:
        """Run an API function on the server.

        Raises:
            AuthError: The server rejected the token.
            RemoteError: The server returned an error or an unexpected HTTP status.
            BackendError: The server cannot be reached.
        """
        with self._lock:
            resp = codec.unpack(self._post(codec.pack({"m": method, "a": args, "k": kwargs})), RECORDS)
        if not resp.get("ok"):
            raise RemoteError(f"{resp.get('t')}: {resp.get('e')}")
        return resp.get("r")

    def ping(self) -> bool:
        """True when the server answers."""
        try:
            return bool(self.call("__ping__", (), {}))
        except Exception:
            return False

    def close(self) -> None:
        """Close the HTTP connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
