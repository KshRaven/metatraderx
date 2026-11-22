# Linux

MetaQuotes ships the Linux terminal as a Wine build and offers no Python API for it. MetaTraderX starts Windows Python
inside the terminal's Wine prefix, runs the official `MetaTrader5` package there and talks to it over an authenticated
loopback socket. The worker is started by `initialize()` and stopped by `shutdown()` or when your program exits. No RPyC
and nothing to start by hand.

## Setup

```
pip install metatraderx
mtx install                    # terminal, and Wine when missing
mtx setup                      # Windows Python and the MetaTrader5 package in the terminal's prefix
mtx terminal list
mtx terminal select 0
mtx doctor
```

`mtx install` uses the official MetaQuotes script on Ubuntu, Debian, Mint and Fedora, and a plain Wine install elsewhere;
see [Install commands](../cli/install.md#mtx-install). Packages are installed with `apt`, `dnf`, `pacman` or `zypper`
after asking, and `sudo` is requested only for that.

```python
import metatraderx as mtx

mtx.initialize()
print(mtx.account_info())
mtx.shutdown()
```

## Terminal and prefix

The terminal can be on any Wine drive; every prefix and its mapped drives are searched. The prefix is derived from the
terminal path. To force one:

```python
mtx.MetaTrader(terminal="/home/me/.wine-mt5/drive_c/Program Files/MetaTrader 5/terminal64.exe",
               prefix="/home/me/.wine-mt5")
```

`MTX_WINEPREFIX`, `MTX_WINE` and `MTX_WINE_PYTHON` override the prefix, the Wine binary and the Windows Python.

## Headless machines

- When no display is available an `Xvfb` virtual screen is started for the worker automatically if `Xvfb` is installed.
  `mtx install` and `mtx setup` install it with Wine.
- To see or control the terminal window, use [`mtx display`](../display.md).
- To use the data from another machine without any of this, [serve](../server/hosting.md) it.

## Notes

- Startup under Wine is slower than on Windows; the first `initialize()` can take up to 90 seconds, later calls on the same
  connection are fast.
- Several terminals can run at once, each as its own [`MetaTrader` instance](../python/metatrader-class.md).
