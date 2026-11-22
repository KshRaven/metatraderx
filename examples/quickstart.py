from __future__ import annotations

import metatraderx as mt5

if not mt5.initialize():
    raise SystemExit(mt5.last_error())
print(mt5.terminal_info())
print(mt5.to_frame(mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 10)))
mt5.shutdown()
