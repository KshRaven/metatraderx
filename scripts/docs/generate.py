"""Writes the generated reference pages (constants, record types) from the package, so they always match the code."""

from __future__ import annotations

import re
from pathlib import Path

import metatraderx as mtx
from metatraderx import constants as C
from metatraderx import types as T

OUT = Path(__file__).resolve().parents[2] / "docs" / "python"

GROUPS = [
    ("Timeframes", "TIMEFRAME_", "Pass to `copy_rates_*`. Minute frames use their minute count; hour frames and above use the terminal's flag values."),
    ("Tick copy flags", "COPY_TICKS_", "The `flags` argument of `copy_ticks_from` and `copy_ticks_range`."),
    ("Tick flags", "TICK_FLAG_", "Bits of the `flags` field of a tick."),
    ("Order actions", "TRADE_ACTION_", "`action` of a trade request."),
    ("Order types", "ORDER_TYPE_", "`type` of a trade request or an order."),
    ("Order filling", "ORDER_FILLING_", "`type_filling` of a trade request."),
    ("Order lifetime", "ORDER_TIME_", "`type_time` of a trade request."),
    ("Order states", "ORDER_STATE_", "`state` of an order."),
    ("Order reasons", "ORDER_REASON_", "`reason` of an order."),
    ("Position types", "POSITION_TYPE_", "`type` of a position."),
    ("Position reasons", "POSITION_REASON_", "`reason` of a position."),
    ("Deal types", "DEAL_TYPE_", "`type` of a deal."),
    ("Deal entries", "DEAL_ENTRY_", "`entry` of a deal."),
    ("Deal reasons", "DEAL_REASON_", "`reason` of a deal."),
    ("Trade return codes", "TRADE_RETCODE_", "`retcode` of `order_check` and `order_send` results."),
    ("Market depth", "BOOK_TYPE_", "`type` of a market depth entry."),
    ("Account", "ACCOUNT_", "Account trade mode, stop-out mode and margin mode values."),
    ("Symbol", "SYMBOL_", "Symbol trade, calculation, swap, option and chart values."),
    ("Days of week", "DAY_OF_WEEK_", "Values used with symbol swap settings."),
    ("Result codes", "RES_", "The code returned first by `last_error()`."),
]

RES_TEXT = {
    "RES_S_OK": "success",
    "RES_E_FAIL": "generic failure",
    "RES_E_INVALID_PARAMS": "invalid arguments",
    "RES_E_NO_MEMORY": "out of memory",
    "RES_E_NOT_FOUND": "nothing found",
    "RES_E_INVALID_VERSION": "invalid version",
    "RES_E_AUTH_FAILED": "authorization failed",
    "RES_E_UNSUPPORTED": "not supported",
    "RES_E_AUTO_TRADING_DISABLED": "algorithmic trading is disabled",
    "RES_E_INTERNAL_FAIL": "internal failure",
    "RES_E_INTERNAL_FAIL_SEND": "internal failure while sending",
    "RES_E_INTERNAL_FAIL_RECEIVE": "internal failure while receiving",
    "RES_E_INTERNAL_FAIL_INIT": "internal failure during initialize",
    "RES_E_INTERNAL_FAIL_CONNECT": "no connection to the terminal",
    "RES_E_INTERNAL_FAIL_TIMEOUT": "timeout",
}


def constants_page() -> str:
    names = sorted(n for n in dir(C) if n.isupper())
    used: set[str] = set()
    out = [
        "# Constants",
        "",
        "Every constant of the official `MetaTrader5` package exists with the same name and value, at module level of",
        "`metatraderx` (`mt5.TIMEFRAME_H1`) and of any alias you import (`mtx.TIMEFRAME_H1`).",
        "",
        "Page generated from the package; do not edit by hand.",
        "",
    ]
    for title, prefix, text in GROUPS:
        items = [n for n in names if n.startswith(prefix) and n not in used]
        if not items:
            continue
        used.update(items)
        if prefix in ("TIMEFRAME_", "RES_"):
            items.sort(key=lambda n: getattr(C, n), reverse=prefix == "RES_")
        out += [f"## {title}", "", text, ""]
        res = prefix == "RES_"
        out += ["| Name | Value |" + (" Meaning |" if res else ""), "| --- | --- |" + (" --- |" if res else "")]
        for n in items:
            extra = f" {RES_TEXT.get(n, '')} |" if res else ""
            out.append(f"| `{n}` | `{getattr(C, n)}` |{extra}")
        out.append("")
    rest = [n for n in names if n not in used]
    if rest:
        out += ["## Other", "", "| Name | Value |", "| --- | --- |", *[f"| `{n}` | `{getattr(C, n)}` |" for n in rest], ""]
    return "\n".join(out)


def types_page() -> str:
    out = [
        "# Result types",
        "",
        "Functions that return one record return a named tuple; functions that return several return a tuple of them.",
        "Fields are read by name (`info.balance`) or by position, and `_asdict()` converts a record to a dict. The same",
        "classes are used whether the data came from a local terminal, a server or the cache.",
        "",
        "Page generated from the package; do not edit by hand.",
        "",
    ]
    for name in sorted(T.RECORDS):
        cls = T.RECORDS[name]
        out += [f"## {name}", "", ", ".join(f"`{f}`" for f in cls._fields), ""]
    out += [
        "## Rates",
        "",
        "`copy_rates_from`, `copy_rates_from_pos` and `copy_rates_range` return a NumPy structured array with the columns "
        "`time` (seconds since 1970, UTC), `open`, `high`, `low`, `close`, `tick_volume`, `spread` and `real_volume`.",
        "",
        "## Ticks",
        "",
        "`copy_ticks_from` and `copy_ticks_range` return a NumPy structured array with the columns "
        "`time`, `bid`, `ask`, `last`, `volume`, `time_msc`, `flags` and `volume_real`.",
        "",
        "## DataFrames",
        "",
        "`to_frame(data)` converts rates, ticks or a list of records to a pandas DataFrame with UTC timestamps "
        "(install with `pip install metatraderx[pandas]`). It exists on the module (`mt5.to_frame`) and on every "
        "`MetaTrader` object (`mt.to_frame`).",
        "",
    ]
    return "\n".join(out)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "constants.md").write_text(constants_page(), encoding="utf-8", newline="\n")
    (OUT / "types.md").write_text(types_page(), encoding="utf-8", newline="\n")
    print("written", len(re.findall(r"^\| `", (OUT / "constants.md").read_text(encoding="utf-8"), re.M)), "constants", mtx.__version__)


if __name__ == "__main__":
    main()
