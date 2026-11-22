# Cache

Fetched data can be stored in a local SQLite file and reused. The cache is off by default.

## Turning it on

| How | Example |
| --- | --- |
| Environment variable | `MTX_CACHE=1` |
| Saved setting | `mtx config cache 1` |
| Constructor | `mtx.MetaTrader(cache=True)` |
| Default instance | `mtx.configure(cache=True)` |
| Command line | `mtx --cache fetch rates EURUSD --tf H1 --count 500` |
| Later, on an instance | `mt.enable_cache()` and `mt.disable_cache()` |

An argument given in code overrides the environment variable, which overrides the saved setting.

```python
import metatraderx as mtx

mt = mtx.MetaTrader(cache=True, cache_ttl=600, cache_dir="D:/mtx-cache")
```

| Option | Meaning | Default |
| --- | --- | --- |
| `cache` | store and reuse data | `MTX_CACHE`, else off |
| `cache_dir` | folder of the cache file | `MTX_CACHE_DIR`, else the [home folder](../reference/environment.md)`/cache` |
| `cache_ttl` | seconds symbol data stays fresh | `MTX_CACHE_TTL`, else `3600` |

## What is cached

| Call | Cached when |
| --- | --- |
| `symbols_total`, `symbols_get`, `symbol_info` | always; reused for `cache_ttl` seconds |
| `copy_rates_range`, `copy_rates_from` | the requested period ended more than two bars ago |
| `copy_ticks_range`, `copy_ticks_from` | the requested period ended more than two minutes ago |

Everything else (quotes, account, orders, positions, history, order calls) is always read live. Periods that are still
open are never stored, so cached bars are always final.

Entries are kept per account scope (the broker company and server), so two brokers never mix.

## Inspecting and clearing

```python
mt.cache_info()                       # {'enabled': True, 'ttl': 3600.0, 'scope': ..., 'path': ..., 'entries': {...}}
mt.clear_cache()                      # everything
mt.clear_cache("copy_rates_range")    # one method
```

```
mtx cache info
mtx cache clear                 # asks first
mtx cache clear -y              # no question
mtx cache clear --method copy_rates_range
```

Cached data is what [offline mode](offline.md) answers from.
