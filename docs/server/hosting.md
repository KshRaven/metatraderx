# Hosting a server

`mtx serve` shares the terminal on this machine over HTTP(S) so other devices can use the same API without installing a
terminal. It runs until Ctrl+C; nothing is installed as a service.

```
mtx serve                                  # 127.0.0.1:8765, this machine only
mtx serve --host 0.0.0.0 --auth auto       # reachable from the network, token generated and printed
mtx serve --auth S3cret --read-only        # no order_send or order_check
mtx serve --allow-login                    # clients may call login()
mtx serve --cert cert.pem --key key.pem    # HTTPS
```

| Option | Meaning |
| --- | --- |
| `--host` | address to bind; default `127.0.0.1` |
| `--port` | default: the first free port from `8765`; the address is printed when it starts |
| `--auth TOKEN` | token clients must send; `auto` generates one |
| `--read-only` | reject `order_send` and `order_check` |
| `--allow-login` | let clients call `login()`; `initialize` and `shutdown` are never exposed |
| `--cert`, `--key` | certificate and key for HTTPS |

A token is required for any address other than loopback. The server uses the terminal chosen with
[`mtx terminal select`](../cli/terminal.md), or the one given with `mtx --terminal PATH serve`.

## Address

| Scheme | Meaning |
| --- | --- |
| `mtx://host:8765` | plain HTTP |
| `mtxs://host:8765` | HTTPS |
| `https://domain/base` | HTTPS behind a reverse proxy, with an optional path |

## From Python

```python
from metatraderx.server import MTXServer
import metatraderx as mtx

mt = mtx.MetaTrader(terminal=r"D:\Acme\terminal64.exe")
mt.initialize()
MTXServer(mt, host="0.0.0.0", port=8765, token="S3cret", read_only=True).serve_forever()
```

## Reverse proxy or domain

Bind to loopback, put nginx, Caddy or a tunnel in front, and give clients the public address:

```
mtx serve --auth S3cret
```

```nginx
location /mtx/ {
    proxy_pass http://127.0.0.1:8765/;
    proxy_set_header Authorization $http_authorization;
}
```

Clients then use `https://example.com/mtx`. Always keep a token on a public address.

Clients are described in [Connecting to a server](clients.md).
