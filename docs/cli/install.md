# Install commands

## mtx install

Downloads the official installer for this system and runs it.

```
mtx install            # MetaTrader 5
mtx install 4          # MetaTrader 4
mtx install 5 -y       # accept the questions
```

| Option | Meaning |
| --- | --- |
| `4`, `5` | MetaTrader version; default `5` |
| `--method auto\|script\|wine` | Linux only, see below |
| `--prefix PATH` | Wine prefix to install into (Linux and macOS, `wine` method) |
| `--dir PATH` | install into `PATH/MetaTrader4` or `PATH/MetaTrader5` instead of the default folder (Windows, Linux, macOS; not with the Linux `script` method) |
| `-y`, `--yes` | answer yes to the questions |
| `--winedebug LEVEL` | Wine log output, before the command: `mtx --winedebug fixme install` |

| System | What happens |
| --- | --- |
| Windows | the installer is downloaded and runs without a window; Windows asks for administrator permission once (run from an elevated shell to avoid the prompt). The terminal the setup starts is closed afterwards |
| macOS | the `.dmg` is downloaded and the app copied to `/Applications`, or to `--dir` |
| Linux, `wine` | Wine is installed with your package manager when missing, then the Windows installer runs silently on a virtual screen (Xvfb) in `~/.mt5` or `~/.mt4`, or in `--prefix`; no window opens. Wine Mono and Gecko prompts are switched off, so nothing waits for input, and each Wine step times out instead of hanging |
| Linux, `auto` | the same as `wine` |
| Linux, `script` | the official MetaQuotes script is run; it installs Wine, opens windows and asks for your password |

Permission questions are asked before anything that needs administrator rights.

A folder given with `--dir` is saved in the `search` setting, so `mtx terminal list` finds the terminal afterwards. A
download that fails Python's TLS verification or times out is retried with `curl` when it is installed.

```
mtx install 4 --dir D:\MT          # D:\MT\MetaTrader4
```

## mtx uninstall

Removes a terminal, official or from any broker.

```
mtx uninstall                 # the selected terminal
mtx uninstall 2               # number from `mtx terminal list`
mtx uninstall "/path/to/terminal64.exe" --data --stop
mtx uninstall 1 --prefix      # the whole Wine prefix (Linux, macOS)
```

| Option | Meaning |
| --- | --- |
| `TARGET` | number from `mtx terminal list`, terminal path or its install folder; default: the selected terminal |
| `--data` | also remove its data folders (MQL files, history) |
| `--prefix` | remove the whole Wine prefix the terminal lives in |
| `--stop` | close the terminal if it is running |
| `--dry-run` | list what would be removed |
| `-y`, `--yes` | do not ask for confirmation |

The install folder and shortcuts are removed; data and the Wine prefix are kept unless asked. On Windows the terminal's own
uninstaller is not opened: the files and the Windows uninstall entries are removed by one hidden script that asks for
administrator permission once, so it also works on a headless machine. Anything that could not be removed is listed.

## mtx download

Saves an installer without running it.

```
mtx download 5 --os linux --dest ~/Downloads
```

| Option | Meaning |
| --- | --- |
| `4`, `5` | version |
| `--os windows\|linux\|macos` | system the installer is for; default this one |
| `--dest DIR` | folder to save to; default the `downloads` folder of the [home folder](../reference/environment.md) |

The path of the saved file is printed. Installers are fetched from MetaQuotes' own download servers.

## mtx setup

Prepares what the Python API needs.

```
mtx setup
mtx setup --prefix ~/.wine-mt5 -y
```

| System | What happens |
| --- | --- |
| Windows | checks the `MetaTrader5` package and offers to install it with pip |
| Linux and macOS | installs Wine if needed, then Windows Python and the `MetaTrader5` package inside the terminal's Wine prefix |

The prefix is that of the selected terminal, or the one given with `--prefix`. Run it once after installing a terminal
on Linux or macOS; see [Linux](../platforms/linux.md) and [macOS](../platforms/macos.md).
