# Connecting

## Which terminal is used

The first match wins:

1. the `path` given to `initialize(path=...)`
2. the `terminal=` given to `MetaTrader(...)`
3. the `url=` given to `MetaTrader(...)`, which uses a [server](../server/clients.md)
4. the saved terminal (`mtx terminal select`) or `MTX_TERMINAL`
5. `MTX_URL` or the saved `url`, which uses a server
6. on Windows with MetaTrader 5, the terminal the official package finds itself
7. otherwise the newest terminal found on the system (all drives are searched)

If nothing is found, `initialize()` returns `False` and `last_error()` reports `no MetaTrader terminal found`.

## Default terminal

```python
import metatraderx as mt5

mt5.initialize()                                  # saved or found terminal
mt5.initialize(login=12345678, password="...", server="Broker-Demo")
mt5.shutdown()
```

## A specific terminal or broker build

Give the executable. It can be any MetaTrader 4 or 5 build, including broker-branded ones:

```python
import metatraderx as mtx

mt = mtx.MetaTrader(terminal="D:/Brokers/Exness/terminal64.exe")
mt.initialize()
```

or hand it to `initialize` on any object or on the module:

```python
mt5.initialize(path="D:/Brokers/Exness/terminal64.exe")
```

The version (4 or 5) is detected from the terminal. Use `version=4` or `version=5` to force it. On Linux and macOS the
Wine prefix is found from the terminal path; pass `prefix="~/.mt5"` when it cannot be (see [Linux](../platforms/linux.md)).

## Logging in

Login details can be given when connecting, later, or to the object:

```python
mt = mtx.MetaTrader(terminal=..., login=12345678, password="...", server="Broker-Demo")
mt.initialize()

mt.initialize()
mt.login(12345678, password="...", server="Broker-Demo")
```

`mtx login` does the same from a shell, see [login](../cli/data.md#login).

## Several terminals at once

Each `MetaTrader` object has its own connection:

```python
a = mtx.MetaTrader(terminal="D:/Brokers/A/terminal64.exe")
b = mtx.MetaTrader(url="mtx://trading-box:8765", token="...")
a.initialize(); b.initialize()
print(a.account_info().login, b.account_info().login)
```

The module-level functions (`mt5.initialize()` and the rest) use a single default object. Replace it with
`mt5.configure(terminal=..., cache=True)`, which takes the same arguments as `MetaTrader`.

## Context manager

```python
with mtx.MetaTrader(terminal="...") as mt:
    print(mt.account_info())
```

`initialize()` runs on entry and `shutdown()` on exit. An `MTXError` is raised if connecting fails.

## MetaTrader 4

Pass an MT4 terminal and the data-only bridge is used. See [MetaTrader 4](../platforms/mt4.md) for the one-time setup
and the functions available.

## Servers

`MetaTrader(url="mtx://host:8765", token="...")` connects to a running `mtx serve`. See
[Connecting to a server](../server/clients.md).
