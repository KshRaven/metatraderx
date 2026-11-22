"""Runs inside Windows Python under Wine, next to the terminal, and serves MetaTrader5 calls over loopback TCP."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]  # types.py, config.py, ... would shadow the standard library

import importlib.util  # noqa: E402
import socket  # noqa: E402


def _codec():
    spec = importlib.util.spec_from_file_location("_mtx_codec", os.path.join(os.path.dirname(os.path.abspath(__file__)), "codec.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_mtx_codec"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    """Connect back to the parent on 127.0.0.1:<port> (argv[1]) with the nonce (argv[2]) and serve calls until told to quit."""
    port, nonce = int(sys.argv[1]), sys.argv[2]
    codec = _codec()
    sock = socket.create_connection(("127.0.0.1", port), 30)
    sock.settimeout(None)
    try:
        import MetaTrader5 as mt5
    except Exception as e:  # noqa: BLE001
        codec.send_frame(sock, codec.pack({"nonce": nonce, "error": f"MetaTrader5 package unavailable: {e}"}))
        return 2
    codec.send_frame(sock, codec.pack({"nonce": nonce, "version": mt5.__version__, "python": sys.version}))
    while True:
        try:
            req = codec.unpack(codec.recv_frame(sock))
        except (ConnectionError, OSError):
            break
        method = req["m"]
        if method == "__quit__":
            break
        try:
            if method == "__ping__":
                res = True
            else:
                fn = getattr(mt5, method, None)
                if method.startswith("_") or not callable(fn):
                    raise AttributeError(method)
                res = fn(*req.get("a", ()), **req.get("k", {}))
            out = {"ok": True, "r": res}
        except Exception as e:  # noqa: BLE001
            out = {"ok": False, "t": type(e).__name__, "e": str(e)}
        try:
            codec.send_frame(sock, codec.pack(out))
        except (ConnectionError, OSError):
            break
    try:
        mt5.shutdown()
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
