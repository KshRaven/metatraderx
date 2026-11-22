# Terminal and account

The functions that connect to the terminal and describe it and the account. Examples use `mt5`; every function is
also a method of [`MetaTrader`](metatrader-class.md).

## initialize

```python
initialize(path=None, login=None, password=None, server=None, timeout=None, portable=None) -> bool
```

Connects to the terminal, starting it if needed.

| Argument | Meaning |
| --- | --- |
| `path` | terminal executable; see [Connecting](connecting.md) for the default |
| `login`, `password`, `server` | account to log into; the terminal's last account is used when omitted |
| `timeout` | milliseconds to wait for the connection |
| `portable` | `True` to start the terminal in portable mode |

Returns `True` on success. On a server connection `path` is ignored; the server's terminal is used. In
[offline mode](../modes/offline.md) it returns `True` without contacting anything.

## login

```python
login(login, password=None, server=None, timeout=None) -> bool
```

Logs the connected terminal into another trade account. On a server connection this works only when the server was
started with `--allow-login`. In offline mode it returns `True`.

## shutdown

```python
shutdown() -> None
```

Closes the connection. A terminal that was already running stays open.

## version

```python
version() -> tuple | None
```

`(terminal version, build, release date)`, for example `(500, 6328, "20 Nov 2026")`.

## last_error

```python
last_error() -> tuple
```

`(code, description)` of the last failure, `(1, "Success")` when there was none. The codes are listed in
[Errors](errors.md).

```python
if not mt5.initialize():
    code, text = mt5.last_error()
```

## terminal_info

```python
terminal_info() -> TerminalInfo | None
```

State and settings of the terminal: connection (`connected`, `ping_last`), permissions (`trade_allowed`,
`dlls_allowed`, `tradeapi_disabled`), build, `company`, `name`, `language` and the folders (`path`, `data_path`,
`commondata_path`). Fields: [TerminalInfo](types.md#terminalinfo).

## account_info

```python
account_info() -> AccountInfo | None
```

The current trade account: `login`, `server`, `name`, `currency`, `leverage`, `balance`, `equity`, `margin`,
`margin_free`, `margin_level`, `profit` and trade permissions. Fields: [AccountInfo](types.md#accountinfo).

```python
acc = mt5.account_info()
print(acc.login, acc.balance, acc.currency)
print(acc._asdict())
```
