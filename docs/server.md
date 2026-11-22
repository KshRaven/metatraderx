# Server and display

## mtx serve

```
mtx serve --host 0.0.0.0 --port 8765 --auth auto --read-only
```

```python
mt = mt5.MetaTrader(url="mtx://host:8765", token="...")
```

`https://domain/base` or `mtxs://` addresses work behind a reverse proxy. A token is required for any address other
than loopback. `initialize` and `shutdown` are never exposed, `login` only with `--allow-login`, and `--read-only`
blocks `order_send` and `order_check`. Use `--cert` and `--key` for built-in TLS.

## mtx display

```
mtx display --host 0.0.0.0 --port 14500
mtx display --tunnel
```

Shows the terminal window in a browser through Xpra until Ctrl+C, then closes it. Non-loopback addresses and tunnels get
a generated password. Xpra (and cloudflared for `--tunnel`) is offered for installation when missing; on Windows Xpra
must be installed first and the whole desktop session is shared.
