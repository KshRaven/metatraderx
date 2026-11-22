"""Linux and macOS backend: Windows Python under Wine next to the terminal, reached over loopback."""

from __future__ import annotations

import atexit
import secrets
import socket
import subprocess
import threading
from pathlib import Path
from typing import Any

from .. import codec, wineenv
from ..discovery import prefix_of
from ..errors import BackendError, SetupError
from ..types import RECORDS
from .base import Backend

__all__ = ["WineBackend"]


class WineBackend(Backend):
    """Linux/macOS: starts Windows Python under Wine in the terminal's prefix and talks to it over loopback.

    The worker is created and stopped automatically; nothing has to be started by hand.
    """

    name = "wine"

    def __init__(self, prefix: str | None = None, wine: str | None = None, python: str | None = None, startup_timeout: float = 90.0):
        """Prepare the backend; start() launches the worker.

        Args:
            prefix: Wine prefix of the terminal. Derived from the terminal path in start() when omitted.
            wine: Wine binary. Found automatically (MTX_WINE) when omitted.
            python: Windows python.exe inside the prefix (MTX_WINE_PYTHON). Found automatically when omitted.
            startup_timeout: Seconds to wait for the worker to connect back.
        """
        self.prefix = Path(prefix) if prefix else None
        self.wine = wine
        self.python = python
        self.startup_timeout = startup_timeout
        self._proc: subprocess.Popen | None = None
        self._xvfb: subprocess.Popen | None = None
        self._sock: socket.socket | None = None
        self._env: dict = {}
        self._lock = threading.RLock()
        self.info: dict = {}
        atexit.register(self.close)

    @property
    def alive(self) -> bool:
        """True while the worker process runs and its socket is open."""
        return self._proc is not None and self._proc.poll() is None and self._sock is not None

    def start(self, terminal_path: str | None = None) -> None:
        """Launch the worker (Windows Python under Wine) and authenticate it; does nothing when already running.

        Args:
            terminal_path: Terminal executable, used to find the Wine prefix when none was given.

        Raises:
            SetupError: Wine, the prefix, Windows Python or the MetaTrader5 package is missing (run `mtx setup`).
            BackendError: The worker did not start in time or failed authentication.
        """
        with self._lock:
            if self.alive:
                return
            prefix = self.prefix or (prefix_of(terminal_path) if terminal_path else None)
            if prefix is None:
                raise SetupError("no Wine prefix found for the terminal; pass prefix= or set MTX_WINEPREFIX")
            self.prefix = prefix
            wine = self.wine or wineenv.wine_bin()
            if not wine:
                raise SetupError("wine was not found; run: mtx setup")
            py = Path(self.python) if self.python else wineenv.wine_python(prefix)
            if not py or not py.is_file():
                raise SetupError(f"Windows Python with MetaTrader5 is not installed in {prefix}; run: mtx setup")
            env = wineenv.base_env(prefix)
            extra, self._xvfb = wineenv.ensure_display()
            env.update(extra)
            self._env, self.wine = env, wine
            worker = Path(__file__).resolve().parent.parent / "_worker.py"
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(self.startup_timeout)
            nonce = secrets.token_hex(16)
            self._proc = subprocess.Popen(
                [wine, str(py), wineenv.to_win_path(wine, env, worker), str(listener.getsockname()[1]), nonce],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                conn, _ = listener.accept()
            except OSError as e:
                self.close()
                raise BackendError("the Wine worker did not start in time") from e
            finally:
                listener.close()
            conn.settimeout(None)
            hello = codec.unpack(codec.recv_frame(conn))
            if hello.get("nonce") != nonce:
                conn.close()
                self.close()
                raise BackendError("the Wine worker failed authentication")
            if hello.get("error"):
                conn.close()
                self.close()
                raise SetupError(hello["error"] + "; run: mtx setup")
            self._sock, self.info = conn, hello

    def call(self, method: str, args: tuple, kwargs: dict) -> Any:
        """Forward an API function to the worker; the terminal path of initialize() is converted to a Windows path.

        Raises:
            BackendError: The worker stopped or the function raised inside it.
        """
        with self._lock:
            if not self.alive:
                raise BackendError("the Wine worker is not running")
            if method == "initialize":
                kwargs = dict(kwargs)
                if kwargs.get("path"):
                    kwargs["path"] = wineenv.to_win_path(self.wine, self._env, kwargs["path"])
            try:
                codec.send_frame(self._sock, codec.pack({"m": method, "a": args, "k": kwargs}))
                resp = codec.unpack(codec.recv_frame(self._sock), RECORDS)
            except (ConnectionError, OSError) as e:
                self.close()
                raise BackendError(f"the Wine worker stopped: {e}") from e
        if not resp.get("ok"):
            raise BackendError(f"{resp.get('t')}: {resp.get('e')}")
        return resp.get("r")

    def close(self) -> None:
        """Ask the worker to quit, then stop it and the virtual screen if one was started."""
        with self._lock:
            if self._sock is not None:
                try:
                    codec.send_frame(self._sock, codec.pack({"m": "__quit__"}))
                except OSError:
                    pass
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None
            if self._proc is not None:
                try:
                    self._proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                self._proc = None
            if self._xvfb is not None:
                self._xvfb.terminate()
                self._xvfb = None
