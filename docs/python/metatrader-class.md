# The MetaTrader class

`import metatraderx as mtx` exposes the same functions as module-level calls (`mtx.initialize()`) and as the
`MetaTrader` class. Use the class when you want a specific terminal, a server or several connections at once. The module
functions use a default instance that is created from the [settings](../reference/environment.md); `mtx.configure(...)`
replaces it.

```python
import metatraderx as mtx

mt = mtx.MetaTrader()                                          # saved or found terminal
mt = mtx.MetaTrader(terminal=r"D:\Brokers\Acme\terminal64.exe")  # a given build
mt = mtx.MetaTrader(url="mtx://10.0.0.5:8765", token="...")      # a server
mt.initialize()
```

`MetaTraderX` is an alias of `MetaTrader`. A terminal version is detected from the executable; MetaTrader 4 terminals
are supported too ([MetaTrader 4](../platforms/mt4.md)).

Every class, method and function carries a docstring, and the module-level functions have type stubs, so editors show
the arguments and descriptions on hover without opening this documentation.

## Constructor

```python
MetaTrader(terminal=None, url=None, token=None, *, version=None, prefix=None, login=None, password=None,
           server=None, timeout=None, portable=None, cache=None, cache_dir=None, cache_ttl=None,
           offline=None, verbose=None, strict=False, read_only=False)
```

| Argument | Meaning |
| --- | --- |
| `terminal` | path to the terminal executable; found automatically when omitted |
| `url` | address of a [server](../server/clients.md) instead of a local terminal |
| `token` | server token |
| `version` | `5` or `4`; detected when omitted |
| `prefix` | Wine prefix (Linux and macOS) |
| `login`, `password`, `server`, `timeout`, `portable` | defaults for `initialize()` |
| `cache`, `cache_dir`, `cache_ttl` | [cache](../modes/cache.md) |
| `offline` | [offline mode](../modes/offline.md) |
| `verbose` | [verbosity](../modes/verbosity.md) |
| `strict` | raise [exceptions](errors.md) instead of returning `None` |
| `read_only` | reject `order_send` and `order_check` on this instance |

## Methods

Every function in the [Python reference](index.md#reference-pages) is a method with the same arguments, plus:

| Method | Returns |
| --- | --- |
| `symbol_names(group=None, first=None, last=None)` | symbol names only |
| `to_frame(data)` | a pandas DataFrame from rates, ticks or records |
| `enable_cache(directory=None, ttl=None)` | turns the cache on |
| `disable_cache()` | turns it off |
| `clear_cache(method=None)` | number of entries removed |
| `cache_info()` | dict describing the cache |
| `connected` | `True` while a connection is open |
| `backend_name` | `native`, `wine`, `remote` or `mt4`; `None` when not connected |

## Context manager

```python
with mtx.MetaTrader(terminal=path) as mt:
    print(mt.account_info())
```

`initialize()` runs on entry and `shutdown()` on exit. Entry raises `MTXError` when initialization fails.

## Several terminals

Each instance has its own connection:

```python
a = mtx.MetaTrader(terminal=r"D:\Acme\terminal64.exe")
b = mtx.MetaTrader(url="mtx://10.0.0.5:8765", token="...")
a.initialize(); b.initialize()
```
