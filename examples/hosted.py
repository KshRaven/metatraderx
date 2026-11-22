from __future__ import annotations

import metatraderx as mtx

mt = mtx.MetaTrader(url="mtx://127.0.0.1:8765", token=None) # (url="localhost:8765")
if not mt.initialize():
    raise SystemExit(mt.last_error())
print(mt.terminal_info())
print(mt.symbol_names(first=5))
print(mt.to_frame(mt.copy_rates_from_pos("EURUSD", mtx.TIMEFRAME_H1, 0, 10)))
mt.shutdown()
