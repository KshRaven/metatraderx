# Connecting to a server

A client needs only this package. Calls run on the server's terminal; the results arrive on your machine as the same
[types](../python/types.md) and arrays, so code does not change.

```python
import metatraderx as mtx

mt = mtx.MetaTrader(url="mtx://10.0.0.5:8765", token="S3cret")
mt.initialize()
print(mt.account_info())
print(mt.to_frame(mt.copy_rates_from_pos("EURUSD", mtx.TIMEFRAME_H1, 0, 10)))
mt.shutdown()
```

| Way | How |
| --- | --- |
| Instance | `mtx.MetaTrader(url=..., token=...)` |
| Module functions | `mtx.configure(url=..., token=...)` |
| Environment | `MTX_URL` and `MTX_TOKEN` |
| Saved setting | `mtx config url mtx://10.0.0.5:8765` and `mtx config token S3cret` |
| Command line | `mtx --url mtx://10.0.0.5:8765 --token S3cret info account` |

`initialize()` checks that the server answers. With `login`, `password` and `server` it calls `login()` on the server,
which the server must have started with `--allow-login`.

## What runs where

| Runs on the server | Arrives on your machine |
| --- | --- |
| terminal, account, orders, positions, trades | rates, ticks, symbols and history as arrays and records |

Trading calls are rejected when the server uses `--read-only`; the client sees `last_error()` report the refusal.

The [cache](../modes/cache.md) and [offline mode](../modes/offline.md) work with a server too, so fetched data can be
used later with the server turned off.

## Errors

| Problem | Result |
| --- | --- |
| server does not answer | `initialize()` returns `False` (`BackendError` with `strict=True`) |
| wrong or missing token | `AuthError` |
| call blocked by the server | `last_error()` explains; `RemoteError` with `strict=True` |

See [Hosting a server](hosting.md) for the server side.
