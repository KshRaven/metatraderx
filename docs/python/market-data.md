# Market data

Symbols, quotes, rates, ticks and market depth. Dates may be `datetime` objects; a `datetime` without a time zone is
treated as UTC, and returned times are UTC. See the [constants](constants.md#timeframes) for timeframes and tick flags.

## symbols_total

```python
symbols_total() -> int | None
```

Number of symbols in the terminal.

## symbols_get

```python
symbols_get(group="") -> tuple[SymbolInfo, ...] | None
```

Every symbol, or those matching `group`, a comma-separated list of patterns where `*` matches any text and `!`
excludes: `"*USD*,!*EUR*"`. Each item is a full [SymbolInfo](types.md#symbolinfo). To get names only use
[`symbol_names`](#symbol_names).

## symbol_names

```python
symbol_names(group=None, first=None, last=None) -> list[str] | None
```

Extra, not in the official package. Only the names, such as `"EURUSD"`, `"XAUUSD"` or `"BTCUSDm"`. `group` filters as
in `symbols_get`; `first=N` keeps the first N names and `last=N` the last N.

```python
mt5.symbol_names(group="*USD*", last=10)
```

## symbol_info

```python
symbol_info(symbol) -> SymbolInfo | None
```

The full specification of one symbol: digits, point, spread, contract size, volume limits, trade modes, swaps,
margins and more.

## symbol_info_tick

```python
symbol_info_tick(symbol) -> Tick | None
```

The latest tick: `time`, `bid`, `ask`, `last`, `volume`, `time_msc`, `flags`, `volume_real`.

## symbol_select

```python
symbol_select(symbol, enable=True) -> bool | None
```

Shows (`True`) or hides (`False`) a symbol in Market Watch. A symbol must be selected before its quotes can be used.

## market_book_add, market_book_get, market_book_release

```python
market_book_add(symbol) -> bool | None
market_book_get(symbol) -> tuple[BookInfo, ...] | None
market_book_release(symbol) -> bool | None
```

Subscribe to market depth, read it, and unsubscribe. Each entry has `type` ([`BOOK_TYPE_*`](constants.md#market-depth)),
`price`, `volume` and `volume_real`.

## copy_rates_from

```python
copy_rates_from(symbol, timeframe, date_from, count) -> ndarray | None
```

`count` bars starting at `date_from` and going back in time.

## copy_rates_from_pos

```python
copy_rates_from_pos(symbol, timeframe, start_pos, count) -> ndarray | None
```

`count` bars starting `start_pos` bars from the newest one (0 is the current bar).

## copy_rates_range

```python
copy_rates_range(symbol, timeframe, date_from, date_to) -> ndarray | None
```

Bars between two dates.

All three return a structured array: [rates columns](types.md#rates). Convert with `mt5.to_frame(rates)`.

```python
from datetime import datetime, timezone

mt5.symbol_select("EURUSD", True)
rates = mt5.copy_rates_range("EURUSD", mt5.TIMEFRAME_M15,
                             datetime(2025, 1, 1, tzinfo=timezone.utc),
                             datetime(2025, 2, 1, tzinfo=timezone.utc))
df = mt5.to_frame(rates)
```

## copy_ticks_from

```python
copy_ticks_from(symbol, date_from, count, flags=-1) -> ndarray | None
```

`count` ticks from `date_from`. `flags` is `COPY_TICKS_ALL`, `COPY_TICKS_INFO` or `COPY_TICKS_TRADE`.

## copy_ticks_range

```python
copy_ticks_range(symbol, date_from, date_to, flags=-1) -> ndarray | None
```

Ticks between two dates. Both return the [ticks columns](types.md#ticks).

## Caching

Symbol data and finished rate or tick ranges can be [cached](../modes/cache.md) and then also work
[offline](../modes/offline.md).
