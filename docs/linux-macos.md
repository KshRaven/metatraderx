# Linux and macOS

MetaQuotes ships the terminal for these systems as a Wine build and offers no Python API for it. MetaTraderX runs
Windows Python with the `MetaTrader5` package in the terminal's Wine prefix and connects to it over loopback.

```
mtx install      # official installer script (Ubuntu, Debian, Mint, Fedora) or Wine plus the Windows installer
mtx setup        # Windows Python and MetaTrader5 inside the prefix
```

On a headless Linux host an Xvfb display is started automatically when `Xvfb` is installed. The default prefix of the
official script is `~/.mt5`. Set `MTX_WINEPREFIX`, `MTX_WINE` or `MTX_WINE_PYTHON` for other layouts.

macOS support is best effort and untested.
