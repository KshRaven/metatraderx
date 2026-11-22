# Python API

Every function and constant of the official `MetaTrader5` package is available at module level and on
`metatraderx.MetaTrader`. Calls return `None` on failure and `last_error()` explains why, as in the official package;
`MetaTrader(strict=True)` raises `MTXError` for connection problems instead.

```python
import metatraderx as mt5

mt = mt5.MetaTrader(terminal="/path/terminal64.exe", cache=True)
mt.initialize()
df = mt5.to_frame(mt.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_M5, 0, 1000))
mt.shutdown()
```

## Choosing the connection

1. `terminal=` or `initialize(path=...)`
2. `url=` (with `token=`)
3. the saved terminal (`mtx terminal select`) or `MTX_TERMINAL`
4. `MTX_URL`
5. the first terminal found on the system (on Windows the official package finds it)

Terminal versions are detected from the folder and the executable; pass `version=4` or `version=5` to force one.

## Cache

`MTX_CACHE=1`, `MetaTrader(cache=True, cache_dir=..., cache_ttl=...)`, `enable_cache()`, `disable_cache()`,
`clear_cache()`, `cache_info()`. Cached: `symbols_total`, `symbols_get`, `symbol_info` (for `cache_ttl` seconds) and
rates or ticks whose end lies in the past. Cached data is also served when the terminal cannot be reached, and
`offline=True` uses only the cache.

## Offline mode

`import metatraderx.offline as mt5` answers every call from the local cache and never contacts a terminal or server. `initialize()` and `login()` return `True`; anything not cached returns `None` with `last_error()` set, and trading calls are unavailable.

```python
import metatraderx.offline as mt5

mt5.initialize()
rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 500)
```

The same mode is available as `metatraderx.configure(offline=True)`, `MTX_OFFLINE=1` for the normal import, and `mtx --offline`.

It is silent by default. `MTX_VERBOSE=1` (or `verbose=1`, `mtx -v`) prints a notice from `initialize`, `login` and `shutdown`; level 2 (`-vv`) also reports each call and whether it came from the cache.
