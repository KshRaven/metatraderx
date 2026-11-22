# MetaTraderX

A universal MetaTrader 5 and MetaTrader 4 Python API for Windows, Linux and macOS. `import metatraderx as mt5` works
like `import MetaTrader5 as mt5`, with the same functions, constants and result types.

On Windows it drives the installed terminal through the official package. On Linux and macOS the terminal is the Wine
build MetaQuotes ships; MetaTraderX starts a worker inside the same Wine prefix and talks to it over an authenticated
loopback socket. The worker starts and stops with your program, so no RPyC server, container or separate process has to
be run by hand.

A device with no terminal can use the same API against a running `mtx serve` on another machine.

## Install

```
pip install metatraderx
mtx install        # MetaTrader 5; `mtx install 4` for MetaTrader 4
mtx setup          # Linux and macOS: Wine, Windows Python and the MetaTrader5 package
mtx terminal list
mtx terminal select 0
```

Broker builds with a custom executable are found too, and any executable can be selected by path.

## Use

```python
import metatraderx as mt5

if not mt5.initialize(login=12345678, password="...", server="Broker-Demo"):
    raise SystemExit(mt5.last_error())

print(mt5.account_info())
print(mt5.to_frame(mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 500)))
mt5.shutdown()
```

A specific terminal or a server, with the `MetaTrader` class:

```python
import metatraderx as mtx

mt = mtx.MetaTrader(terminal="/home/me/.mt5/drive_c/Program Files/MetaTrader 5/terminal64.exe")
mt = mtx.MetaTrader(url="mtx://trading-box:8765", token="...")
mt.initialize()
```

## Command line

```
mtx symbols --first 20
mtx fetch rates EURUSD --tf M15 --from 2025-01-01 --to 2025-02-01 -o eurusd.csv
mtx fetch deals --from -30d -o deals.json
mtx serve --host 0.0.0.0 --auth auto --read-only
mtx display --tunnel
```

The command line has no trading commands.

## Documentation

https://kshraven.github.io/metatraderx/

| | |
| --- | --- |
| [Installation](docs/install.md) | terminal, Wine and package setup |
| [Python API](docs/python/index.md) | functions, constants, result types, the `MetaTrader` class |
| [Cache](docs/modes/cache.md), [Offline mode](docs/modes/offline.md), [Verbosity](docs/modes/verbosity.md) | keeping data and working without a terminal |
| [Server](docs/server/hosting.md) and [clients](docs/server/clients.md) | sharing a terminal |
| [Terminal display](docs/display.md) | the terminal window in a browser |
| [Command line](docs/cli/index.md) | every `mtx` command |
| [Platforms](docs/platforms/windows.md) | Windows, Linux, macOS, MetaTrader 4 |
| [Settings](docs/reference/environment.md) | environment variables and saved settings |

## MetaTrader 4

MetaTrader 4 has no Python API. Read-only data (account, symbols, rates, positions, deal history) is available through
the bundled `MetaTraderXBridge` expert, which is experimental. See [MetaTrader 4](docs/platforms/mt4.md).

## Notice

MetaTraderX is an independent project and is not affiliated with or endorsed by MetaQuotes Ltd. MetaTrader is a
trademark of MetaQuotes Ltd. Trading carries risk, and the software is provided as is under the licence below.

## Licence

MIT
