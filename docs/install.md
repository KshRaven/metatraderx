# Installation

```
pip install metatraderx
pip install "metatraderx[pandas]"    # adds DataFrame support (mt5.to_frame)
```

Python 3.10 or newer. The install provides two identical commands, `mtx` (short) and `metatraderx`, plus
`python -m metatraderx`. On Windows the official `MetaTrader5` package is installed with it.

## 1. Get a terminal

If a terminal is already installed, skip this step. Otherwise let `mtx` download and install it for your system:

```
mtx install          # MetaTrader 5
mtx install 4        # MetaTrader 4
```

`mtx download` only downloads the installer. See [install, download and setup](cli/install.md) for the options and for
what happens on each system.

## 2. Prepare Linux and macOS

```
mtx setup
```

This installs what the Wine build needs to be controlled from Python: Wine, a virtual display for headless machines, and
Windows Python with the `MetaTrader5` package inside the terminal's Wine prefix. It asks before using administrator
rights. Windows needs nothing here. Details: [Linux](platforms/linux.md), [macOS](platforms/macos.md).

## 3. Choose the terminal

```
mtx terminal list
mtx terminal select 0
```

All drives are searched, so a terminal installed on `D:` or in a custom folder is listed. Broker builds with a custom
executable name are found too. See [terminal commands](cli/terminal.md).

On Windows this step is optional: without a selection the official package uses the terminal it finds itself.

## 4. Check

```
mtx doctor
mtx info terminal
```

`mtx doctor` prints the system, Python, Wine, the selected terminal and the helper programs. If something fails, see
[Troubleshooting](troubleshooting.md).

## Next

Continue with [Using the package](python/index.md).
