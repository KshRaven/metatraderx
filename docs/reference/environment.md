# Settings

Each setting is taken from an argument in code when one is given, otherwise from the environment variable
`MTX_<NAME>`, otherwise from the saved config file, otherwise the default. Saved settings are managed with [`mtx config`](../cli/tools.md#config).

```
mtx config terminal "D:\Brokers\Acme\terminal64.exe"
mtx config cache 1
mtx config                # list
```

| Setting | Environment variable | Meaning | Default |
| --- | --- | --- | --- |
| `terminal` | `MTX_TERMINAL` | terminal executable | found automatically |
| `version` | `MTX_VERSION` | `4` or `5` | detected |
| `url` | `MTX_URL` | [server](../server/clients.md) address | none |
| `token` | `MTX_TOKEN` | server token | none |
| `cache` | `MTX_CACHE` | turn the [cache](../modes/cache.md) on | off |
| `cache_dir` | `MTX_CACHE_DIR` | cache folder | `<home>/cache` |
| `cache_ttl` | `MTX_CACHE_TTL` | seconds symbol data stays fresh | `3600` |
| `offline` | `MTX_OFFLINE` | [offline mode](../modes/offline.md) | off |
| `verbose` | `MTX_VERBOSE` | [verbosity](../modes/verbosity.md) | `0` |
| `search` | `MTX_SEARCH` | extra folders searched for terminals (`;` on Windows, `:` elsewhere) | none |
| `wine` | `MTX_WINE` | Wine binary (Linux, macOS) | found on `PATH` |
| `wineprefix` | `MTX_WINEPREFIX` | Wine prefix (Linux, macOS) | from the terminal path |
| `winedebug` | `MTX_WINEDEBUG` | Wine log output: `all` (silent), `fixme` (errors shown), `off` (Wine defaults) or a raw `WINEDEBUG` value | `all` |
| `wine_python` | `MTX_WINE_PYTHON` | Windows Python inside the prefix | found in the prefix |
| `mt4_port` | `MTX_MT4_PORT` | [MetaTrader 4](../platforms/mt4.md) bridge port | `5555` |

Booleans accept `1`, `true`, `yes`, `on` and `0`, `false`, `no`, `off`.

## Other variables

| Variable | Meaning |
| --- | --- |
| `MTX_HOME` | folder for settings, downloads, cache and the default Wine prefix |
| `MTX_URL_MT5_WINDOWS`, `MTX_URL_MT5_LINUX`, `MTX_URL_MT5_MACOS`, `MTX_URL_MT4_*` | installer download address, for a mirror or a broker installer |

## Home folder

| System | Default |
| --- | --- |
| Windows | `%LOCALAPPDATA%\metatraderx` |
| Linux | `$XDG_DATA_HOME/metatraderx`, else `~/.local/share/metatraderx` |
| macOS | `~/Library/Application Support/metatraderx` |

It holds `config.json`, `cache/`, `downloads/` and, on Linux and macOS, the default Wine prefixes.
