# Offline mode

Offline mode answers only from the [cache](cache.md). No terminal is started and no server is contacted, so it works on
a machine that has neither. Turning it on also turns the cache on.

## Turning it on

```python
import metatraderx.offline as mt5        # the whole module is offline
```

```python
import metatraderx as mtx

mt = mtx.MetaTrader(offline=True)         # one instance
mtx.configure(offline=True)               # the module-level functions
```

```
MTX_OFFLINE=1 python script.py           # no code change
mtx --offline fetch rates EURUSD --tf H1 --from 2025-01-01 --to 2025-02-01
```

## Behaviour

| Call | Result |
| --- | --- |
| `initialize()`, `login()`, `shutdown()` | succeed without contacting anything; the last account scope used online is restored |
| `symbols_total`, `symbols_get`, `symbol_info` | answered from the cache |
| `copy_rates_*`, `copy_ticks_*` | answered when the same request was fetched earlier; `None` otherwise |
| quotes, account, orders, positions, history, trading calls | not available; `None` |

When a call cannot be answered `last_error()` returns `(-4, 'offline: not in cache')`. Nothing is raised, so code written
for a live terminal keeps running; it only receives `None` where data is missing.

The requested range must match what was cached: a request is answered when the same method was called earlier with the
same arguments while online with the cache on.

## Notices

Offline mode is silent by default. Set [verbosity](verbosity.md) to see it:

```python
mtx.configure(offline=True, verbose=1)
```

```
[mtx] offline mode: initialize() uses cached data only (scope 'MetaQuotes Ltd.|MetaQuotes-Demo'); no terminal is contacted
```
