# MetaTraderX

A universal MetaTrader 5 and MetaTrader 4 Python API for Windows, Linux and macOS. It has the same functions, constants
and result types as the official `MetaTrader5` package, and works on systems where that package does not.

```python
import metatraderx as mt5

mt5.initialize()
print(mt5.account_info())
print(mt5.symbol_names(first=5))
mt5.shutdown()
```

## What it does

| You want to | Read |
| --- | --- |
| Install the package and a terminal | [Installation](install.md) |
| Use it like `import MetaTrader5 as mt5` | [Using the package](python/index.md) |
| Pick a terminal, a broker build or a server | [Connecting](python/connecting.md) |
| Look up a function, constant or result type | [Python reference](python/index.md#reference-pages) |
| Keep fetched data and work without a terminal | [Cache](modes/cache.md), [Offline mode](modes/offline.md), [Verbosity](modes/verbosity.md) |
| Share one terminal with other machines | [Hosting a server](server/hosting.md), [Connecting to a server](server/clients.md) |
| See the terminal window in a browser | [Terminal display](display.md) |
| Do the same from a shell | [Command line](cli/index.md) |
| Set up Windows, Linux, macOS or MetaTrader 4 | [Platforms](platforms/windows.md) |
| Look up an environment variable | [Settings](reference/environment.md) |
| Fix a problem | [Troubleshooting](troubleshooting.md) |

## How it connects

- **Windows:** the installed terminal is driven through the official `MetaTrader5` package, which is installed with
  MetaTraderX.
- **Linux and macOS:** MetaQuotes ships the terminal as a Wine build and offers no Python API for it. MetaTraderX runs
  Windows Python with the `MetaTrader5` package inside the terminal's Wine prefix and talks to it over an authenticated
  loopback socket. The worker starts and stops with your program; nothing has to be run by hand and no RPyC is used.
- **A server:** a device that has no terminal can connect to a running [`mtx serve`](server/hosting.md) and use the same
  functions. Data arrives on your device and orders are executed on the server.
- **Offline:** with the [cache](modes/cache.md) on, previously fetched data can be used without any terminal or server.
