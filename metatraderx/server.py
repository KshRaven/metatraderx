"""HTTP(S) server that exposes one terminal connection to other machines or processes (`mtx serve`)."""

from __future__ import annotations

import hmac
import ipaddress
import json
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from . import codec
from ._version import __version__
from .backends.base import API, TRADING
from .client import MetaTrader
from .errors import MTXError

__all__ = ["MTXServer", "is_loopback"]

MAX_BODY = 64 << 20
_BLOCKED = {"initialize", "shutdown"}


def is_loopback(host: str) -> bool:
    """True for localhost and loopback addresses, which may be served without a token."""
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class MTXServer:
    """Serves the MetaTrader API of `client` at POST /rpc and GET /health.

    token         required for any non-loopback bind
    read_only     reject order_send and order_check
    allow_login   let clients call login(); initialize and shutdown are never exposed
    certfile      PEM certificate (with keyfile) to serve HTTPS directly
    """

    def __init__(
        self,
        client: MetaTrader,
        host: str = "127.0.0.1",
        port: int = 8765,
        token: str | None = None,
        read_only: bool = False,
        allow_login: bool = False,
        certfile: str | None = None,
        keyfile: str | None = None,
    ) -> None:
        """Bind the server socket; serving starts with start() or serve_forever().

        Args:
            client: The connected MetaTrader instance to expose.
            host: Address to bind.
            port: Port to bind; 0 picks a free one (see the port attribute).
            token: Token clients must send. Required for a non-loopback host.
            read_only: Reject order_send and order_check.
            allow_login: Let clients call login().
            certfile: PEM certificate to serve HTTPS directly.
            keyfile: Private key for certfile.

        Raises:
            MTXError: A non-loopback host without a token.
        """
        if not token and not is_loopback(host):
            raise MTXError("a token is required when binding to a non-loopback address")
        self.client, self.host, self.token = client, host, token
        self.read_only, self.allow_login = read_only, allow_login
        self._lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            """Serves /health and /rpc for the terminal API."""

            protocol_version = "HTTP/1.1"
            server_version = f"MetaTraderX/{__version__}"

            def log_message(self, *a: Any) -> None:
                pass

            def _send(self, status: int, body: bytes, ctype: str = "application/x-mtx") -> None:
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _authed(self) -> bool:
                if not outer.token:
                    return True
                got = self.headers.get("Authorization", "")
                return got.startswith("Bearer ") and hmac.compare_digest(got[7:], outer.token)

            def do_GET(self) -> None:
                """Answer /health."""
                if self.path.rstrip("/") != "/health":
                    return self._send(404, b"not found", "text/plain")
                if not self._authed():
                    return self._send(401, b"unauthorized", "text/plain")
                body = json.dumps(
                    {"status": "ok", "version": __version__, "backend": outer.client.backend_name, "connected": outer.client.connected}
                ).encode()
                self._send(200, body, "application/json")

            def do_POST(self) -> None:
                """Answer /rpc calls."""
                if self.path.rstrip("/") != "/rpc":
                    self.close_connection = True
                    return self._send(404, b"not found", "text/plain")
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > MAX_BODY:
                    self.close_connection = True
                    return self._send(413, b"bad length", "text/plain")
                raw = self.rfile.read(n)
                if not self._authed():
                    return self._send(401, b"unauthorized", "text/plain")
                try:
                    req = codec.unpack(raw)
                    out = outer.dispatch(req["m"], tuple(req.get("a", ())), dict(req.get("k", {})))
                except Exception as e:  # noqa: BLE001
                    out = {"ok": False, "t": type(e).__name__, "e": str(e)}
                self._send(200, codec.pack(out))

        self.httpd = ThreadingHTTPServer((host, port), Handler)
        self.httpd.daemon_threads = True
        if certfile:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile, keyfile)
            self.httpd.socket = ctx.wrap_socket(self.httpd.socket, server_side=True)
        self.port = self.httpd.server_address[1]
        self.tls = bool(certfile)
        self._thread: threading.Thread | None = None

    def dispatch(self, method: str, args: tuple, kwargs: dict) -> dict:
        """Run one request against the client and return the response dict; MTXError when the method is not allowed."""
        if method == "__ping__":
            return {"ok": True, "r": True}
        if method not in API or method in _BLOCKED or (method == "login" and not self.allow_login):
            raise MTXError(f"{method} is not available on this server")
        if self.read_only and method in TRADING:
            raise MTXError("this server is read-only")
        with self._lock:
            res = getattr(self.client, method)(*args, **kwargs)
        return {"ok": True, "r": res}

    @property
    def url(self) -> str:
        """Address clients use: mtx://host:port, or mtxs:// when serving TLS."""
        h = "127.0.0.1" if self.host in ("0.0.0.0", "::") else self.host
        return f"{'mtxs' if self.tls else 'mtx'}://{h}:{self.port}"

    def serve_forever(self) -> None:
        """Serve in the calling thread until stop() or an interrupt."""
        self.httpd.serve_forever()

    def start(self) -> MTXServer:
        """Serve in a background thread and return self."""
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        """Stop serving and close the socket."""
        self.httpd.shutdown()
        self.httpd.server_close()
