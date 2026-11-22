# Terminal commands

A terminal is the MetaTrader executable (`terminal64.exe` or `terminal.exe`). Brokers often ship their own build, which
is found and selected the same way as the official one; the executable also decides the MetaTrader version.

```
mtx terminal list
mtx terminal select 2
mtx terminal select "D:\Brokers\Acme\terminal64.exe"
mtx terminal show
mtx terminal clear
```

| Action | Does |
| --- | --- |
| `list` | every terminal found, numbered, with its version; the selected one is marked `*` |
| `select N` or `select PATH` | use that terminal from now on; saved in the config file |
| `show` | the selected path, or `none selected` |
| `clear` | forget the selection |

```
 0  MT5  * D:\Applications\MetaTrader5\terminal64.exe
 1  MT4    C:\Program Files\Acme MT4\terminal.exe
```

## Where it looks

| System | Searched |
| --- | --- |
| Windows | every fixed and removable drive, plus the terminals recorded in the MetaQuotes data folders |
| Linux and macOS | every Wine prefix with all of its mapped drives (`C:`, `D:`, ...), plus the recorded terminals |

A terminal installed on `D:` is found as well as one on `C:`. To search another folder add it to `MTX_SEARCH`
(separated by `;` on Windows, `:` elsewhere):

```
MTX_SEARCH=/mnt/tools mtx terminal list
```

## Without selecting

Selection is optional. A single run can name its terminal, and so can code:

```
mtx --terminal "D:\Brokers\Acme\terminal64.exe" info account
```

```python
mtx.MetaTrader(terminal=r"D:\Brokers\Acme\terminal64.exe")
```

The order in which a terminal is chosen is listed in [Connecting](../python/connecting.md#which-terminal-is-used).
