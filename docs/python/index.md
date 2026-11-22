# Using the package

## Two ways to import

**The default terminal, like the official package.** Import it as `mt5` and call functions on the module:

```python
import metatraderx as mt5

if not mt5.initialize():
    raise SystemExit(mt5.last_error())
rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 500)
mt5.shutdown()
```

This is a drop-in replacement for `import MetaTrader5 as mt5`. It connects to the terminal you selected with
`mtx terminal select`, or, on Windows, to the one the official package finds.

**A specific terminal, a server or special modes.** Import it as `mtx` and create a `MetaTrader` object. Every function
is a method of the object, and you can hold several objects at once:

```python
import metatraderx as mtx

mt = mtx.MetaTrader(terminal="D:/Brokers/Exness/terminal64.exe")      # a given terminal or broker build
srv = mtx.MetaTrader(url="mtx://trading-box:8765", token="...")        # a server instead of a local terminal
old = mtx.MetaTrader(offline=True)                                      # cached data only

mt.initialize()
print(mt.account_info())
mt.shutdown()
```

`mt5` is only a naming convention for the default; any alias works. Constants are available on both
(`mt5.TIMEFRAME_H1`, `mtx.TIMEFRAME_H1`).

| | `import metatraderx as mt5` | `import metatraderx as mtx` + `MetaTrader(...)` |
| --- | --- | --- |
| Terminal | saved or found automatically | the one you give |
| Server | `MTX_URL` or `configure(url=...)` | `MetaTrader(url=...)` |
| Several at once | no | yes |
| Modes | `configure(...)`, environment variables | constructor arguments |

For a ready-made offline module see [Offline mode](../modes/offline.md).

## Results and errors

Like the official package, functions return `None` or `False` when something fails, and `last_error()` tells you why.
Pass `strict=True` to `MetaTrader` to raise exceptions instead. See [Errors](errors.md).

## Reference pages

| Page | Contents |
| --- | --- |
| [Connecting](connecting.md) | choosing a terminal, `initialize` arguments, logging in, several terminals |
| [Terminal and account](account-terminal.md) | `initialize`, `login`, `shutdown`, `version`, `last_error`, `terminal_info`, `account_info` |
| [Market data](market-data.md) | symbols, ticks, rates, market depth, `symbol_names` |
| [Trading and history](trading.md) | orders, positions, `order_check`, `order_send`, history |
| [The MetaTrader class](metatrader-class.md) | constructor arguments, properties, cache methods, extras |
| [Result types](types.md) | records, rates and ticks, DataFrames |
| [Constants](constants.md) | every constant with its value |
| [Errors](errors.md) | exceptions and result codes |

Other features have their own sections: [cache, offline and verbosity](../modes/cache.md),
[server](../server/hosting.md), [terminal display](../display.md) and the [command line](../cli/index.md).
