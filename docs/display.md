# Terminal display

`mtx display` shows the real terminal window in a browser, for a machine with no screen or when you want the terminal
from another device. It runs until Ctrl+C, then closes the terminal. It is temporary on purpose; wrap it in your own
service file if you need it permanent.

```
mtx display                    # http://127.0.0.1:14500/
mtx display --port 15000
mtx display --host 0.0.0.0 --password S3cret
mtx display --tunnel           # temporary public https link
```

| Option | Meaning |
| --- | --- |
| `--host` | address to bind; default `127.0.0.1` |
| `--force` | close a running terminal (and anything else in its Wine prefix) first; for headless servers |
| `--port` | default: the first free port from `14500` (Xpra's own service may hold `14500`) |
| `--password` | password for the page; generated and printed when the page is public |
| `--tunnel` | temporary public `https` link through Cloudflare, closed on exit |
| `-y`, `--yes` | install missing dependencies without asking |

A password is always set when `--tunnel` is used or the address is not loopback. The terminal comes from
[`mtx terminal select`](cli/terminal.md) or `mtx --terminal PATH display`.

## What it needs

| Need | Windows | Linux | macOS |
| --- | --- | --- | --- |
| [Xpra](https://xpra.org/) with the HTML5 client | install from xpra.org | installed with `apt`, `dnf`, `pacman` or `zypper` after asking | `brew install --cask xpra` after asking |
| Wine | not used; the installed terminal is shown | installed by `mtx setup` or `mtx install` | same as Linux |
| `cloudflared`, for `--tunnel` only | downloaded after asking | downloaded after asking | `brew install cloudflared` |

On Debian and Ubuntu the official xpra.org repository is added, and kept only when its packages install on the system.
When it has no repository for the release, or its packages do not fit, nearby releases are tried. If none fits, install
a supported release or Xpra from [xpra.org](https://xpra-org.github.io/xpra/Download/).

Missing packages are offered one at a time. Administrator or `sudo` permission is requested only when a package manager
needs it, and `-y` accepts the questions.

- **Windows** shares the whole desktop (`xpra shadow`); Xpra has no per-window mode there. The terminal opens on that
  desktop, and opening the page on the same machine shows the browser inside itself. Open it from another device
  (`--host 0.0.0.0` with a password, or `--tunnel`). The desktop must stay unlocked, so a server needs an active session.
- **Linux and macOS** start a private virtual screen and run the terminal inside it under Wine, so nothing appears on the
  machine's own display.

## Headless Linux

```
mtx install
mtx display --tunnel
```

Open the printed link on any device and sign in with the printed password. Use the page to log in to an account, switch
on algorithmic trading, or anything else the terminal can do. Close with Ctrl+C on the server.

Trading from code is still done with the [Python functions](python/trading.md); the terminal must have algorithmic
trading enabled (`terminal_info().trade_allowed`), which can be switched on through this page.
