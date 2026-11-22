# Command line

`mtx` (or `python -m metatraderx`) does the one-off jobs from a shell: installing a terminal, choosing which one to use,
logging in, saving data to files, sharing the terminal and showing its window. Trading commands do not exist; order
functions are available from [Python](../python/trading.md) only.

```
mtx [global options] <command> [options]
```

## Commands

| Command | Does | Page |
| --- | --- | --- |
| `install`, `uninstall`, `download`, `setup` | get or remove a terminal and prepare Wine | [Install](install.md) |
| `terminal` | list and select terminal executables | [Terminal](terminal.md) |
| `login`, `info`, `symbols`, `symbol`, `fetch` | account and market data, saved as files | [Data](data.md) |
| `serve` | share the terminal over HTTP(S) | [Hosting a server](../server/hosting.md) |
| `display` | show the terminal window in a browser | [Terminal display](../display.md) |
| `cache`, `config`, `mt4`, `doctor` | cache, settings, MetaTrader 4 bridge, diagnosis | [Tools](tools.md) |

## Global options

They go before the command.

| Option | Meaning |
| --- | --- |
| `--terminal PATH` | terminal executable for this run instead of the selected one |
| `--url URL` | use a [server](../server/clients.md) instead of a local terminal |
| `--token TOKEN` | server token |
| `--cache` | use the [cache](../modes/cache.md) for this command |
| `--offline` | answer from the cache only ([offline mode](../modes/offline.md)) |
| `-v`, `-vv` | [verbosity](../modes/verbosity.md) for offline notices |
| `-V`, `--version` | package version |
| `-h`, `--help` | help; also works after any command |

```
mtx --terminal D:\Acme\terminal64.exe info account
mtx --url mtx://10.0.0.5:8765 --token S3cret symbols --first 10
mtx --offline -v fetch rates EURUSD --tf H1 --count 200 -o eurusd.csv
```

## Output

Commands that return data print to the screen, or write a file with `-o`. The format follows the file extension
(`.csv`, `.json`, `.jsonl`, and `.txt` for symbol names) or `--format`. Times are written as ISO dates in UTC; add
`--raw-time` to keep the integer timestamps.

## Dates

`--from` and `--to` accept `now`, a relative time such as `-30d`, `-12h`, `-90m` or `-2w`, a date `2025-01-31`, or a
date and time `2025-01-31T10:30`. Times are UTC.
