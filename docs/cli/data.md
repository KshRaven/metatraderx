# Data commands

These start the terminal, read, and close it. Every command accepts the [global options](index.md#global-options), so the
same commands also work against a [server](../server/clients.md) or from the [cache](../modes/cache.md).

Common output options:

| Option | Meaning |
| --- | --- |
| `-o FILE`, `--out FILE` | write a file; the extension chooses the format |
| `--format csv\|json\|jsonl` | format when printing or when the extension does not say |
| `--raw-time` | keep timestamps as integers |

## login

```
mtx login --login 12345678 --server Broker-Demo
mtx login --login 12345678 --server Broker-Demo --password "..."
```

Logs the terminal into an account. The password is asked for when `--password` is not given. Prints the account and
server on success. Not available for MetaTrader 4, where the account is chosen inside the terminal.

## info

```
mtx info account
mtx info terminal -o terminal.json
mtx info version
```

`account` and `terminal` give the fields of [`account_info`](../python/account-terminal.md#account_info) and
[`terminal_info`](../python/account-terminal.md#terminal_info). `version` prints the terminal version.

## symbols

Lists symbol names, one per line.

```
mtx symbols
mtx symbols --group "*USD*,!*EUR*" --first 20
mtx symbols --last 10 -o names.txt
mtx symbols --full -o symbols.csv
```

| Option | Meaning |
| --- | --- |
| `--group PATTERN` | filter; `*` matches any text and `!` excludes |
| `--first N`, `--last N` | only the first or last N |
| `--full` | every field of each symbol instead of the name |
| `--format txt\|csv\|json\|jsonl` | default `txt`, or the file extension |

```
XAUUSD
EURUSDm
BTCUSD
```

## symbol

The full specification of one symbol.

```
mtx symbol EURUSD
mtx symbol XAUUSD -o xauusd.json
```

## fetch

Saves market data and history.

```
mtx fetch rates EURUSD --tf M15 --from 2025-01-01 --to 2025-02-01 -o eurusd.csv
mtx fetch rates EURUSD --tf H1 --count 500 -o recent.csv
mtx fetch rates EURUSD --tf D1 --pos 10 --count 100
mtx fetch ticks EURUSD --from -1d --to now --flags trade -o ticks.jsonl
mtx fetch deals --from -30d -o deals.json
mtx fetch orders --from -90d --group "*USD*"
```

| Kind | Needs | Notes |
| --- | --- | --- |
| `rates SYMBOL` | `--tf`, then `--from` and `--to`, or `--from` and `--count`, or `--pos` and `--count` | `--tf` is `M1`..`M30`, `H1`..`H12`, `D1`, `W1`, `MN1` and the other [timeframes](../python/constants.md#timeframes); default `H1`. Without dates, `--count` bars (default 1000) from position `--pos` (default 0) |
| `ticks SYMBOL` | `--from`; `--to` or `--count` | `--flags all\|info\|trade`; default `all` |
| `deals` | none | history deals; default the last 30 days |
| `orders` | none | history orders; default the last 30 days; `--group` filters by symbol pattern |

The symbol is selected in Market Watch automatically. The number of rows written is printed.

Deals and orders are read-only history; there are no trading commands.
