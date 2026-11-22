# Troubleshooting

Start with:

```
mtx doctor
```

It shows the system, Python, Wine, the selected terminal, the saved settings and which helpers are installed.

| Problem | Cause and fix |
| --- | --- |
| `no terminals found` | none installed, or none on the searched drives. Run `mtx install`, or add a folder to `MTX_SEARCH`, or give the path with `mtx terminal select PATH` |
| `no MetaTrader terminal found` from `initialize()` | no terminal could be chosen. Select one with `mtx terminal select` or pass `terminal=` |
| `initialize()` returns `False` | read `last_error()`. On Linux and macOS the first start can take up to 90 seconds |
| `metatraderx is not set up on this system` (Linux, macOS) | run `mtx setup` once; `mtx doctor` shows what is missing on its `setup` line |
| `wine was not found; run: mtx setup` | install Wine with `mtx setup`, or set `MTX_WINE` |
| `no Wine prefix found for the terminal` | the terminal is not inside a Wine prefix; pass `prefix=` or set `MTX_WINEPREFIX` |
| `login` fails | check the server name exactly as the terminal shows it, and that the account is for that broker |
| `trade_allowed` is `False` | switch on algorithmic trading in the terminal. A [display page](display.md) can be used on a headless machine |
| orders rejected on a server | the server runs with `--read-only` |
| `AuthError` | the token does not match the server's `--auth` |
| `a token is required when binding to a non-loopback address` | add `--auth auto` (or a token) when using `--host 0.0.0.0` |
| `mtx display` asks for Xpra | install it from xpra.org on Windows; Linux and macOS offer to install it |
| offline call returns `None` | that request was never cached. Fetch it once online with the [cache](modes/cache.md) on |
| the MetaTrader 4 call is not supported | the bridge covers a subset; see [MetaTrader 4](platforms/mt4.md#supported) |

When reporting a problem include the output of `mtx doctor` and the exact error.
