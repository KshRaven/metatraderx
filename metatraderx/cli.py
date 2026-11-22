"""mtx: install, select and inspect MetaTrader terminals, fetch data, serve the API, show the terminal GUI."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from . import __version__, config, discovery, installer, wineenv
from . import constants as C
from .client import MetaTrader
from .errors import MTXError
from .export import parse_dt, parse_tf, to_rows, write_rows

CONFIG_KEYS = (
    "terminal", "url", "token", "version", "cache", "cache_dir", "cache_ttl", "wine", "wineprefix", "wine_python",
    "mt4_port", "search", "offline", "verbose", "winedebug",
)  # fmt: skip


class CLIError(Exception):
    """A user-facing command line error; main() prints it as `mtx: <message>` and exits with 1."""
    pass


def _client(a: argparse.Namespace, **kw: Any) -> MetaTrader:
    mt = MetaTrader(
        terminal=a.terminal, url=a.url, token=a.token, cache=True if a.cache else None, offline=True if a.offline else None, verbose=a.verbose or None, strict=True, **kw
    )
    if not mt.initialize():
        raise CLIError(f"could not connect: {mt.last_error()}")
    return mt


def _emit(data: Any, a: argparse.Namespace) -> None:
    if data is None:
        raise CLIError("no data returned")
    write_rows(to_rows(data, getattr(a, "raw_time", False)), getattr(a, "out", None), getattr(a, "format", None))


def _selected(a: argparse.Namespace) -> str:
    t = a.terminal or config.setting("terminal")
    if not t:
        raise CLIError("no terminal selected; run: mtx terminal list, then mtx terminal select")
    return str(t)


# -- commands -----------------------------------------------------------------------------------------------------
def c_install(a: argparse.Namespace) -> int:
    """mtx install: download and install the terminal."""
    installer.install(a.version, a.yes, a.prefix, a.method)
    return 0


def c_uninstall(a: argparse.Namespace) -> int:
    """mtx uninstall: remove a terminal (number from `mtx terminal list`, a path, or the selected one)."""
    from .uninstall import uninstall

    target = a.target
    if target and target.isdigit():
        found = discovery.find_terminals()
        if int(target) >= len(found):
            raise CLIError("no such entry; run: mtx terminal list")
        target = found[int(target)]["path"]
    removed = uninstall(target, a.yes, a.data, a.prefix, a.stop, a.dry_run)
    print(("would remove " if a.dry_run else "removed ") + f"{len(removed)} item(s)")
    for r in removed if a.dry_run else ():
        print(f"  {r}")
    return 0


def c_download(a: argparse.Namespace) -> int:
    """mtx download: fetch an installer without running it."""
    print(installer.download(a.version, a.os, a.dest))
    return 0


def c_setup(a: argparse.Namespace) -> int:
    """mtx setup: prepare Wine, Windows Python and the MetaTrader5 package (the package only, on Windows)."""
    if config.IS_WIN:
        try:
            import MetaTrader5  # noqa: F401
        except ImportError:
            import subprocess

            if installer.ask("Install the MetaTrader5 package with pip?", a.yes):
                subprocess.check_call([sys.executable, "-m", "pip", "install", "MetaTrader5"])
        print("ready")
        return 0
    term = a.terminal or config.setting("terminal")
    pre = Path(a.prefix) if a.prefix else (discovery.prefix_of(term) if term else None)
    if pre is None:
        found = [t for t in discovery.find_terminals() if t["prefix"]]
        pre = Path(found[0]["prefix"]) if found else Path.home() / ".mt5"
    py = installer.setup_wine_python(pre, a.yes)
    print(f"ready: {py}")
    return 0


def c_terminal(a: argparse.Namespace) -> int:
    """mtx terminal list | select | show | clear."""
    act = a.action
    if act == "list":
        found = discovery.find_terminals()
        if not found:
            print("no terminals found; install one with: mtx install")
        cur = config.setting("terminal")
        for i, t in enumerate(found):
            print(f"{i:>2}  MT{t['version'] or '?'}  {'*' if t['path'] == cur else ' '} {t['path']}")
        return 0
    if act == "show":
        print(config.setting("terminal") or "none selected")
        return 0
    cfg = config.load()
    if act == "clear":
        for k in ("terminal", "version"):
            cfg.pop(k, None)
        config.save(cfg)
        return 0
    if not a.target:
        raise CLIError("give a path or a number from `mtx terminal list`")
    if a.target.isdigit():
        found = discovery.find_terminals()
        if int(a.target) >= len(found):
            raise CLIError("no such entry; run: mtx terminal list")
        path = found[int(a.target)]["path"]
    else:
        path = str(Path(a.target).expanduser().resolve())
        if not Path(path).is_file():
            raise CLIError(f"{path} does not exist")
    ver = discovery.terminal_version(path)
    cfg["terminal"] = path
    if ver:
        cfg["version"] = ver
    config.save(cfg)
    print(f"selected MT{ver or '?'}: {path}")
    return 0


def c_login(a: argparse.Namespace) -> int:
    """mtx login: connect the terminal to an account."""
    pw = a.password if a.password is not None else getpass.getpass("Password: ")
    mt = MetaTrader(terminal=a.terminal, url=a.url, token=a.token, strict=True)
    if not mt.initialize(login=a.login, password=pw, server=a.server):
        raise CLIError(f"login failed: {mt.last_error()}")
    info = mt.account_info()
    print(f"logged in: {info.login} on {info.server} ({info.name})" if info else "connected")
    mt.shutdown()
    return 0


def c_info(a: argparse.Namespace) -> int:
    """mtx info account | terminal | version."""
    mt = _client(a)
    try:
        data = {"account": mt.account_info, "terminal": mt.terminal_info, "version": lambda: mt.version()}[a.what]()
        if a.what == "version":
            print(".".join(map(str, data[:2])) if data else "unknown")
            return 0
        _emit(data, a)
    finally:
        mt.shutdown()
    return 0


def c_symbols(a: argparse.Namespace) -> int:
    """mtx symbols: symbol names, or every field with --full."""
    if a.first is not None and a.last is not None:
        raise CLIError("use --first or --last, not both")
    mt = _client(a)
    try:
        if a.full:
            res = mt.symbols_get(group=a.group) if a.group else mt.symbols_get()
            if res is not None and a.first is not None:
                res = res[: max(a.first, 0)]
            elif res is not None and a.last is not None:
                res = res[-a.last :] if a.last > 0 else []
            _emit(res, a)
            return 0
        names = mt.symbol_names(a.group, a.first, a.last)
    finally:
        mt.shutdown()
    if names is None:
        raise CLIError("no data returned")
    fmt = a.format or (Path(a.out).suffix.lstrip(".").lower() if a.out else "txt")
    if fmt == "csv":
        body = "name\n" + "".join(n + "\n" for n in names)
    elif fmt == "json":
        body = json.dumps(names, indent=2) + "\n"
    elif fmt == "jsonl":
        body = "".join(json.dumps(n) + "\n" for n in names)
    else:
        body = "".join(n + "\n" for n in names)
    if a.out and a.out != "-":
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(body, encoding="utf-8", newline="")
        print(f"{len(names)} symbols -> {a.out}", file=sys.stderr)
    else:
        sys.stdout.write(body)
    return 0


def c_symbol(a: argparse.Namespace) -> int:
    """mtx symbol: one symbol's specification."""
    mt = _client(a)
    try:
        if not mt.symbol_select(a.symbol, True):
            raise CLIError(f"unknown symbol {a.symbol}")
        _emit(mt.symbol_info(a.symbol), a)
    finally:
        mt.shutdown()
    return 0


def c_fetch(a: argparse.Namespace) -> int:
    """mtx fetch rates | ticks | deals | orders: save data to a file or stdout."""
    mt = _client(a)
    try:
        k = a.kind
        if k in ("rates", "ticks"):
            mt.symbol_select(a.symbol, True)
        if k == "rates":
            tf = parse_tf(a.tf)
            if a.start and a.end:
                data = mt.copy_rates_range(a.symbol, tf, parse_dt(a.start), parse_dt(a.end))
            elif a.start:
                data = mt.copy_rates_from(a.symbol, tf, parse_dt(a.start), a.count)
            else:
                data = mt.copy_rates_from_pos(a.symbol, tf, a.pos, a.count)
        elif k == "ticks":
            flags = {"all": C.COPY_TICKS_ALL, "info": C.COPY_TICKS_INFO, "trade": C.COPY_TICKS_TRADE}[a.flags]
            if not a.start:
                raise CLIError("ticks need --from")
            data = (
                mt.copy_ticks_range(a.symbol, parse_dt(a.start), parse_dt(a.end), flags)
                if a.end
                else mt.copy_ticks_from(a.symbol, parse_dt(a.start), a.count, flags)
            )
        else:
            start, end = parse_dt(a.start or "-30d"), parse_dt(a.end or "now")
            fn = mt.history_deals_get if k == "deals" else mt.history_orders_get
            data = fn(start, end, group=a.group) if a.group else fn(start, end)
        _emit(data, a)
    finally:
        mt.shutdown()
    return 0


def c_serve(a: argparse.Namespace) -> int:
    """mtx serve: share the terminal API over HTTP(S) until interrupted."""

    token = a.token_value
    if token == "auto":
        import secrets

        token = secrets.token_urlsafe(24)
        print(f"token: {token}")
    mt = _client(a, read_only=a.read_only)
    srv = _bind(a, mt, token)
    print(f"serving {mt.backend_name} terminal at {srv.url}   (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()
        mt.shutdown()
    return 0


def _bind(a: argparse.Namespace, mt: Any, token: str | None) -> Any:
    """The server on the requested port, or on the first free port from 8765 when none was requested."""
    from .server import MTXServer

    for port in [a.port] if a.port else range(8765, 8865):
        try:
            return MTXServer(mt, a.host, port, token, a.read_only, a.allow_login, a.cert, a.key)
        except OSError as e:
            if a.port:
                raise CLIError(f"port {port} is unavailable: {e.strerror or e}; choose another with --port") from e
    raise CLIError("no free port from 8765 to 8864; choose one with --port")


def c_display(a: argparse.Namespace) -> int:
    """mtx display [setup]: show the terminal in a browser, or install what that needs."""
    from .display import serve_display, setup_display

    if a.action == "setup":
        for k, v in setup_display(a.yes, a.tunnel).items():
            print(f"{k:<12} {v or 'missing'}")
        print("ready")
        return 0
    return serve_display(_selected(a), a.host, a.port, a.password, a.tunnel, a.yes, a.force)


def c_cache(a: argparse.Namespace) -> int:
    """mtx cache info | clear."""
    mt = MetaTrader(cache=True)
    if a.action == "clear":
        info = mt.cache_info()
        entries = info.get("entries", {})
        n = sum(v["count"] for k, v in entries.items() if not a.method or k == a.method)
        what = f"the cached {a.method} data" if a.method else "ALL cached data"
        if not installer.ask(f"This permanently deletes {what} ({n} entries) in {info.get('path')}. Continue?", a.yes, False):
            print("cancelled; nothing was removed", file=sys.stderr)
            return 1
        print(f"removed {mt.clear_cache(a.method)} entries")
    else:
        print(json.dumps(mt.cache_info(), indent=2))
    return 0


def c_config(a: argparse.Namespace) -> int:
    """mtx config [key [value]]: show or change saved settings."""
    cfg = config.load()
    if a.key is None:
        print(json.dumps({k: ("***" if k == "token" else v) for k, v in cfg.items()}, indent=2))
        print(f"file: {config.config_file()}")
        return 0
    if a.key not in CONFIG_KEYS:
        raise CLIError("keys: " + ", ".join(CONFIG_KEYS))
    if a.value is None:
        print(cfg.get(a.key, ""))
    elif a.value == "":
        cfg.pop(a.key, None)
        config.save(cfg)
    else:
        cfg[a.key] = a.value
        config.save(cfg)
    return 0


def c_mt4(a: argparse.Namespace) -> int:
    """mtx mt4 install-bridge: copy the bridge expert into the terminal."""
    from .backends.mt4 import install_bridge

    for p in install_bridge(_selected(a)):
        print(f"copied {p}")
    print("Open MetaEditor, compile MetaTraderXBridge, attach it to a chart with Allow DLL imports enabled.")
    return 0


def c_doctor(a: argparse.Namespace) -> int:
    """mtx doctor: print what this system provides."""
    from .display import find_cloudflared, find_xpra

    info = {
        **installer.platform_summary(),
        "metatraderx": __version__,
        "home": str(config.home(False)),
        "terminal": config.setting("terminal"),
        "url": config.setting("url"),
        "cache": config.env_bool(config.setting("cache"), False),
        "offline": config.env_bool(config.setting("offline"), False),
        "xpra": find_xpra(),
        "cloudflared": find_cloudflared(),
    }
    if config.IS_WIN:
        try:
            import MetaTrader5

            info["MetaTrader5"] = MetaTrader5.__version__
        except ImportError:
            info["MetaTrader5"] = None
    else:
        pre = discovery.prefix_of(info["terminal"]) if info["terminal"] else None
        py = wineenv.wine_python(pre)
        info["prefix"] = str(pre) if pre else None
        info["wine_python"] = str(py) if py else None
        info["xvfb"] = shutil.which("Xvfb")
        info["setup"] = "; ".join(wineenv.setup_problems(info["terminal"], python=True)) or "ready"
    for k, v in info.items():
        print(f"{k:<13} {v}")
    return 0


# -- parser ---------------------------------------------------------------------------------------------------------
def _out(p: argparse.ArgumentParser) -> None:
    p.add_argument("-o", "--out", help="file to write (.csv, .json, .jsonl); stdout when omitted")
    p.add_argument("--format", choices=["csv", "json", "jsonl"])
    p.add_argument("--raw-time", action="store_true", help="keep timestamps as integers")


def build_parser() -> argparse.ArgumentParser:
    """The argument parser of the `mtx` command."""
    ap = argparse.ArgumentParser(prog="mtx", description="MetaTraderX command line")
    ap.add_argument("-V", "--version", action="version", version=f"mtx {__version__}")
    ap.add_argument("--terminal", help="terminal executable to use (default: the selected one)")
    ap.add_argument("--url", help="MetaTraderX server instead of a local terminal")
    ap.add_argument("--token", help="server token")
    ap.add_argument("--cache", action="store_true", help="use the data cache for this command")
    ap.add_argument("--offline", action="store_true", help="answer from the cache only")
    ap.add_argument("--winedebug", metavar="LEVEL", help="Wine log output: all (silent, default), fixme (show errors), off (Wine defaults) or a raw WINEDEBUG value")
    ap.add_argument("-v", "--verbose", action="count", default=0, help="report offline activity (-vv for every call)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("install", help="download and install MetaTrader for this system")
    p.add_argument("version", nargs="?", type=int, choices=[4, 5], default=5)
    p.add_argument("--method", choices=["auto", "script", "wine"], default="auto")
    p.add_argument("--prefix", help="Wine prefix (Linux, wine method)")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(fn=c_install)

    p = sub.add_parser("uninstall", help="remove a terminal, including a broker's own build")
    p.add_argument("target", nargs="?", help="number from `mtx terminal list`, terminal path or its folder (default: the selected terminal)")
    p.add_argument("--data", action="store_true", help="also remove its data folders (MQL files, history)")
    p.add_argument("--prefix", action="store_true", help="Linux and macOS: remove the whole Wine prefix")
    p.add_argument("--stop", action="store_true", help="close the terminal if it is running")
    p.add_argument("--dry-run", action="store_true", help="only list what would be removed")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(fn=c_uninstall)

    p = sub.add_parser("download", help="download an installer without running it")
    p.add_argument("version", nargs="?", type=int, choices=[4, 5], default=5)
    p.add_argument("--os", choices=["windows", "linux", "macos"])
    p.add_argument("--dest")
    p.set_defaults(fn=c_download)

    p = sub.add_parser("setup", help="prepare Wine, Windows Python and the MetaTrader5 package")
    p.add_argument("--prefix")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(fn=c_setup)

    p = sub.add_parser("terminal", help="list or select the terminal executable")
    p.add_argument("action", choices=["list", "select", "show", "clear"])
    p.add_argument("target", nargs="?", help="path to the executable, or its number from the list")
    p.set_defaults(fn=c_terminal)

    p = sub.add_parser("login", help="log the terminal into an account")
    p.add_argument("--login", type=int, required=True)
    p.add_argument("--password")
    p.add_argument("--server", required=True)
    p.set_defaults(fn=c_login)

    p = sub.add_parser("info", help="account, terminal or version information")
    p.add_argument("what", choices=["account", "terminal", "version"])
    _out(p)
    p.set_defaults(fn=c_info)

    p = sub.add_parser("symbols", help="list symbol names (--full for every field)")
    p.add_argument("--group", help='filter, e.g. "*USD*,!*EUR*"')
    p.add_argument("--first", type=int, metavar="N", help="only the first N symbols")
    p.add_argument("--last", type=int, metavar="N", help="only the last N symbols")
    p.add_argument("--full", action="store_true", help="every field of each symbol instead of only the name")
    p.add_argument("-o", "--out", help="file to write (.txt, .csv, .json, .jsonl); stdout when omitted")
    p.add_argument("--format", choices=["txt", "csv", "json", "jsonl"], help="default: txt, or the file extension")
    p.add_argument("--raw-time", action="store_true", help="with --full: keep timestamps as integers")
    p.set_defaults(fn=c_symbols)

    p = sub.add_parser("symbol", help="symbol specification")
    p.add_argument("symbol")
    _out(p)
    p.set_defaults(fn=c_symbol)

    p = sub.add_parser("fetch", help="save rates, ticks, deals or orders history to a file")
    p.add_argument("kind", choices=["rates", "ticks", "deals", "orders"])
    p.add_argument("symbol", nargs="?")
    p.add_argument("--tf", default="H1", help="M1 M5 M15 M30 H1 H4 D1 W1 MN1 ...")
    p.add_argument("--from", dest="start")
    p.add_argument("--to", dest="end")
    p.add_argument("--count", type=int, default=1000)
    p.add_argument("--pos", type=int, default=0)
    p.add_argument("--flags", choices=["all", "info", "trade"], default="all")
    p.add_argument("--group")
    _out(p)
    p.set_defaults(fn=c_fetch)

    p = sub.add_parser("serve", help="share the terminal API over HTTP(S) until Ctrl+C")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, help="default: the first free port from 8765")
    p.add_argument("--auth", dest="token_value", metavar="TOKEN", help="token clients must send, or 'auto' to generate one")
    p.add_argument("--read-only", action="store_true", help="reject order_send and order_check")
    p.add_argument("--allow-login", action="store_true", help="let clients call login()")
    p.add_argument("--cert")
    p.add_argument("--key")
    p.set_defaults(fn=c_serve)

    p = sub.add_parser("display", help="open the terminal GUI in a browser until Ctrl+C, or install what it needs")
    p.add_argument("action", nargs="?", choices=["run", "setup"], default="run", help="setup installs Xpra and the other requirements")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, help="default: the first free port from 14500")
    p.add_argument("--password")
    p.add_argument("--force", action="store_true", help="close the running terminal and anything else in its Wine prefix first, for headless servers")
    p.add_argument("--tunnel", action="store_true", help="temporary public https link through cloudflared (with setup: install cloudflared)")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(fn=c_display)

    p = sub.add_parser("cache", help="data cache information or removal")
    p.add_argument("action", choices=["info", "clear"])
    p.add_argument("--method", help="only this method's entries, e.g. copy_rates_range")
    p.add_argument("-y", "--yes", action="store_true", help="clear without asking")
    p.set_defaults(fn=c_cache)

    p = sub.add_parser("config", help="show or change saved settings")
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?", help='new value ("" removes it)')
    p.set_defaults(fn=c_config)

    p = sub.add_parser("mt4", help="MetaTrader 4 bridge expert")
    p.add_argument("action", choices=["install-bridge"])
    p.set_defaults(fn=c_mt4)

    p = sub.add_parser("doctor", help="diagnose this system")
    p.set_defaults(fn=c_doctor)
    return ap


def _join_relative(argv: list[str]) -> list[str]:
    """Let `--from -30d` work: argparse would read -30d as an option."""
    out: list[str] = []
    for i, x in enumerate(argv):
        if out and out[-1] in ("--from", "--to") and x.startswith("-") and len(x) > 1:
            out[-1] = f"{out[-1]}={x}"
        else:
            out.append(x)
    return out


def main(argv: list[str] | None = None) -> int:
    """Run the command line (argv defaults to sys.argv[1:]) and return the exit code."""
    a = build_parser().parse_args(_join_relative(list(sys.argv[1:] if argv is None else argv)))
    if a.winedebug is not None:
        os.environ["MTX_WINEDEBUG"] = a.winedebug
    try:
        return int(a.fn(a) or 0)
    except (CLIError, MTXError, ValueError) as e:
        print(f"mtx: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
