# MetaTrader 4

MetaTrader 4 has no Python API of its own, so MetaTraderX reads data through a small expert advisor, the bridge, that
runs inside the terminal. This is experimental and read-only.

## Setup

```
mtx install 4
mtx mt4 install-bridge
```

Then in the terminal:

1. Open MetaEditor (F4), open `MQL4/Experts/MetaTraderXBridge.mq4` and compile it (F7).
2. Attach `MetaTraderXBridge` from the Navigator to any chart, tick **Allow DLL imports** on the Common tab and enable algorithmic trading.

```python
import metatraderx as mtx

mt4 = mtx.MetaTrader(terminal=r"C:\Program Files\Acme MT4\terminal.exe", version=4)
mt4.initialize()
print(mt4.account_info())
print(mt4.to_frame(mt4.copy_rates_from_pos("EURUSD", mtx.TIMEFRAME_H1, 0, 10)))
mt4.shutdown()
```

MetaTraderX listens on `127.0.0.1:5555`; change it with `MTX_MT4_PORT` and the bridge's `Port` input.

## Supported

| Available | Not available |
| --- | --- |
| `initialize`, `shutdown`, `version`, `last_error` | `login` (log in inside the terminal) |
| `account_info`, `terminal_info` | `copy_rates_from`, `copy_ticks_from`, `copy_ticks_range` |
| `symbols_total`, `symbols_get`, `symbol_info`, `symbol_info_tick`, `symbol_select` | market depth |
| `copy_rates_from_pos`, `copy_rates_range` (M1 to MN1) | `orders_get`, order calculation and every trading call |
| `positions_total`, `positions_get` | `history_orders_*` |
| `history_deals_total`, `history_deals_get` | |

A call that is not available returns `None`, and `last_error()` says it is not supported for MetaTrader 4 (an exception
with `strict=True`).

The [cache](../modes/cache.md) and a [server](../server/hosting.md) work with the bridge like with MetaTrader 5.
