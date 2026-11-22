# Windows

MetaTraderX drives the installed terminal through the official `MetaTrader5` package, which is installed with it.

## Setup

```
pip install metatraderx
mtx install                # skip if a terminal is already installed
mtx terminal list
mtx terminal select 0
mtx doctor
```

The installer runs without a window and asks Windows for administrator permission once. Use `--dir D:\MT` for another
folder. A terminal on any drive is found; see
[Terminal commands](../cli/terminal.md).

```python
import metatraderx as mtx

mtx.initialize()
print(mtx.terminal_info())
mtx.shutdown()
```

## Notes

- The official package supports MetaTrader 5 only. A terminal found to be MetaTrader 4 is used through the
  [MetaTrader 4](mt4.md) bridge.
- Broker builds work: give their `terminal64.exe` with `mtx terminal select` or `terminal=`.
- To show the window of a terminal on a headless Windows machine see [Terminal display](../display.md), which needs
  Xpra.
- To use the data on another machine, share the terminal with [`mtx serve`](../server/hosting.md).
