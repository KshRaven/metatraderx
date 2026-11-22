# mtx

| Command | Purpose |
| --- | --- |
| `mtx install [4\|5]` | download and install the terminal for this system |
| `mtx uninstall [TARGET]` | remove a terminal, including a broker's own build |
| `mtx download [4\|5] --os windows` | download an installer only |
| `mtx setup` | Wine, Windows Python and MetaTrader5 for the terminal's prefix |
| `mtx terminal list\|select\|show\|clear` | find and choose the terminal executable (decides MT4 or MT5 and official or broker build) |
| `mtx login --login N --server S` | log the terminal into an account |
| `mtx info account\|terminal\|version` | information |
| `mtx symbols`, `mtx symbol NAME` | symbols and specifications |
| `mtx fetch rates\|ticks\|deals\|orders` | save data as `.csv`, `.json` or `.jsonl` |
| `mtx serve` | share the API over HTTP(S) until Ctrl+C |
| `mtx display` | terminal window in a browser until Ctrl+C |
| `mtx cache info\|clear` | cache |
| `mtx config [key [value]]` | saved settings |
| `mtx doctor` | diagnose this system |

Dates accept `now`, `-7d`, `2025-01-31` and `2025-01-31T10:30` (UTC). There are no trading commands.
