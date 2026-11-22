# Trading and history

Orders, positions and history. Sending orders is done with the Python functions only; the [command line](../cli/index.md)
has no trading commands. The terminal must allow algorithmic trading (`terminal_info().trade_allowed`).

On a [server](../server/clients.md) these calls run on the server's terminal and are rejected when the server was
started with `--read-only`. In [offline mode](../modes/offline.md) `order_send` and `order_check` are unavailable.

## orders_total, orders_get

```python
orders_total() -> int | None
orders_get(symbol=None, group=None, ticket=None) -> tuple[TradeOrder, ...] | None
```

Active (pending) orders: their number, or the orders, filtered by symbol, by a [group pattern](market-data.md#symbols_get)
or by ticket.

## positions_total, positions_get

```python
positions_total() -> int | None
positions_get(symbol=None, group=None, ticket=None) -> tuple[TradePosition, ...] | None
```

Open positions, with the same filters.

## order_calc_margin

```python
order_calc_margin(action, symbol, volume, price) -> float | None
```

Margin needed for a trade. `action` is `ORDER_TYPE_BUY` or `ORDER_TYPE_SELL`.

## order_calc_profit

```python
order_calc_profit(action, symbol, volume, price_open, price_close) -> float | None
```

Profit of a trade in the account currency.

## order_check

```python
order_check(request) -> OrderCheckResult | None
```

Checks a trade request without sending it: funds, margin and parameters. `retcode` 0 means the request can be sent.

## order_send

```python
order_send(request) -> OrderSendResult | None
```

Sends a trade request. Check `result.retcode` against [`TRADE_RETCODE_*`](constants.md#trade-return-codes); `10009` is
done.

`request` is a dict:

| Key | Meaning |
| --- | --- |
| `action` | [`TRADE_ACTION_*`](constants.md#order-actions) |
| `symbol` | symbol name |
| `volume` | lots |
| `type` | [`ORDER_TYPE_*`](constants.md#order-types) |
| `price` | price; the current quote for market orders |
| `sl`, `tp` | stop loss and take profit prices |
| `deviation` | maximum slippage in points |
| `magic` | expert identifier |
| `comment` | order comment |
| `type_time` | [`ORDER_TIME_*`](constants.md#order-lifetime) |
| `type_filling` | [`ORDER_FILLING_*`](constants.md#order-filling) |
| `position`, `order` | ticket to modify or close |
| `expiration` | expiry of a pending order |

```python
tick = mt5.symbol_info_tick("EURUSD")
req = {
    "action": mt5.TRADE_ACTION_DEAL, "symbol": "EURUSD", "volume": 0.01,
    "type": mt5.ORDER_TYPE_BUY, "price": tick.ask, "deviation": 20,
    "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
}
if mt5.order_check(req).retcode == 0:
    print(mt5.order_send(req))
```

## history_orders_total, history_orders_get

```python
history_orders_total(date_from, date_to) -> int | None
history_orders_get(date_from=None, date_to=None, group=None, ticket=None, position=None) -> tuple[TradeOrder, ...] | None
```

Orders from the history, by period (optionally with a group pattern), or by `ticket` or `position`.

## history_deals_total, history_deals_get

```python
history_deals_total(date_from, date_to) -> int | None
history_deals_get(date_from=None, date_to=None, group=None, ticket=None, position=None) -> tuple[TradeDeal, ...] | None
```

Deals from the history, with the same arguments. Closed history periods can be [cached](../modes/cache.md).

```python
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)
deals = mt5.history_deals_get(now - timedelta(days=30), now)
```
