# Result types

Functions that return one record return a named tuple; functions that return several return a tuple of them.
Fields are read by name (`info.balance`) or by position, and `_asdict()` converts a record to a dict. The same
classes are used whether the data came from a local terminal, a server or the cache.

Page generated from the package; do not edit by hand.

## AccountInfo

`login`, `trade_mode`, `leverage`, `limit_orders`, `margin_so_mode`, `trade_allowed`, `trade_expert`, `margin_mode`, `currency_digits`, `fifo_close`, `balance`, `credit`, `profit`, `equity`, `margin`, `margin_free`, `margin_level`, `margin_so_call`, `margin_so_so`, `margin_initial`, `margin_maintenance`, `assets`, `liabilities`, `commission_blocked`, `name`, `server`, `currency`, `company`

## BookInfo

`type`, `price`, `volume`, `volume_dbl`

## OrderCheckResult

`retcode`, `balance`, `equity`, `profit`, `margin`, `margin_free`, `margin_level`, `comment`, `request`

## OrderSendResult

`retcode`, `deal`, `order`, `volume`, `price`, `bid`, `ask`, `comment`, `request_id`, `retcode_external`, `request`

## SymbolInfo

`custom`, `chart_mode`, `select`, `visible`, `session_deals`, `session_buy_orders`, `session_sell_orders`, `volume`, `volumehigh`, `volumelow`, `time`, `digits`, `spread`, `spread_float`, `ticks_bookdepth`, `trade_calc_mode`, `trade_mode`, `start_time`, `expiration_time`, `trade_stops_level`, `trade_freeze_level`, `trade_exemode`, `swap_mode`, `swap_rollover3days`, `margin_hedged_use_leg`, `expiration_mode`, `filling_mode`, `order_mode`, `order_gtc_mode`, `option_mode`, `option_right`, `bid`, `bidhigh`, `bidlow`, `ask`, `askhigh`, `asklow`, `last`, `lasthigh`, `lastlow`, `volume_real`, `volumehigh_real`, `volumelow_real`, `option_strike`, `point`, `trade_tick_value`, `trade_tick_value_profit`, `trade_tick_value_loss`, `trade_tick_size`, `trade_contract_size`, `trade_accrued_interest`, `trade_face_value`, `trade_liquidity_rate`, `volume_min`, `volume_max`, `volume_step`, `volume_limit`, `swap_long`, `swap_short`, `margin_initial`, `margin_maintenance`, `session_volume`, `session_turnover`, `session_interest`, `session_buy_orders_volume`, `session_sell_orders_volume`, `session_open`, `session_close`, `session_aw`, `session_price_settlement`, `session_price_limit_min`, `session_price_limit_max`, `margin_hedged`, `price_change`, `price_volatility`, `price_theoretical`, `price_greeks_delta`, `price_greeks_theta`, `price_greeks_gamma`, `price_greeks_vega`, `price_greeks_rho`, `price_greeks_omega`, `price_sensitivity`, `basis`, `category`, `currency_base`, `currency_profit`, `currency_margin`, `bank`, `description`, `exchange`, `formula`, `isin`, `name`, `page`, `path`

## TerminalInfo

`community_account`, `community_connection`, `connected`, `dlls_allowed`, `trade_allowed`, `tradeapi_disabled`, `email_enabled`, `ftp_enabled`, `notifications_enabled`, `mqid`, `build`, `maxbars`, `codepage`, `ping_last`, `community_balance`, `retransmission`, `company`, `name`, `language`, `path`, `data_path`, `commondata_path`

## Tick

`time`, `bid`, `ask`, `last`, `volume`, `time_msc`, `flags`, `volume_real`

## TradeDeal

`ticket`, `order`, `time`, `time_msc`, `type`, `entry`, `magic`, `position_id`, `reason`, `volume`, `price`, `commission`, `swap`, `profit`, `fee`, `symbol`, `comment`, `external_id`

## TradeOrder

`ticket`, `time_setup`, `time_setup_msc`, `time_done`, `time_done_msc`, `time_expiration`, `type`, `type_time`, `type_filling`, `state`, `magic`, `position_id`, `position_by_id`, `reason`, `volume_current`, `volume_initial`, `price_open`, `price_stoplimit`, `sl`, `tp`, `price_current`, `symbol`, `comment`, `external_id`

## TradePosition

`ticket`, `time`, `time_msc`, `time_update`, `time_update_msc`, `type`, `magic`, `identifier`, `reason`, `volume`, `price_open`, `sl`, `tp`, `price_current`, `swap`, `profit`, `symbol`, `comment`, `external_id`

## TradeRequest

`action`, `magic`, `order`, `symbol`, `volume`, `price`, `stoplimit`, `sl`, `tp`, `deviation`, `type`, `type_filling`, `type_time`, `expiration`, `comment`, `position`, `position_by`

## Rates

`copy_rates_from`, `copy_rates_from_pos` and `copy_rates_range` return a NumPy structured array with the columns `time` (seconds since 1970, UTC), `open`, `high`, `low`, `close`, `tick_volume`, `spread` and `real_volume`.

## Ticks

`copy_ticks_from` and `copy_ticks_range` return a NumPy structured array with the columns `time`, `bid`, `ask`, `last`, `volume`, `time_msc`, `flags` and `volume_real`.

## DataFrames

`to_frame(data)` converts rates, ticks or a list of records to a pandas DataFrame with UTC timestamps (install with `pip install metatraderx[pandas]`). It exists on the module (`mt5.to_frame`) and on every `MetaTrader` object (`mt.to_frame`).
