# Errors

By default a failed call returns `None` and `last_error()` describes why, as in the official package:

```python
if not mt5.initialize():
    print(mt5.last_error())        # (-10003, 'no MetaTrader terminal found; ...')
```

With `strict=True` problems are raised instead:

```python
mt = mtx.MetaTrader(strict=True)
```

| Exception | Raised when |
| --- | --- |
| `MTXError` | base class of all the others |
| `TerminalNotFound` | no terminal could be found |
| `SetupError` | Wine, Windows Python or the `MetaTrader5` package is missing or failed to install; on Linux and macOS also raised by `initialize()` when `mtx setup` has not been run |
| `BackendError` | the terminal connection failed, or the call is not supported (for example `login` on MetaTrader 4) |
| `NotConnected` | a call was made before `initialize()` |
| `RemoteError` | the server answered with an error |
| `AuthError` | the server rejected the token; subclass of `RemoteError` |

`SetupWarning` (a `UserWarning`) is issued when `initialize()` returns `False` for a setup problem, so it is not missed.

All are importable from `metatraderx`. Error codes returned by `last_error()` are listed in
[constants](constants.md) under `RES_E_*`.
