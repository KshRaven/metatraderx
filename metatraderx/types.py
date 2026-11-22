"""Result record types, matching the field names and order of the official MetaTrader5 package.

Each record is a named tuple: read fields by name (`info.balance`) or position, and use `_asdict()` for a dict.
"""

from __future__ import annotations

from typing import NamedTuple


class TerminalInfo(NamedTuple):
    """Status and settings of the terminal, returned by terminal_info()."""

    community_account: bool
    """Whether an MQL5.community account is set up."""
    community_connection: bool
    """Whether the terminal is connected to the MQL5.community."""
    connected: bool
    """Whether the terminal is connected to a trade server."""
    dlls_allowed: bool
    """Whether DLL imports are allowed."""
    trade_allowed: bool
    """Whether algorithmic trading is allowed."""
    tradeapi_disabled: bool
    """Whether trading through the API is disabled."""
    email_enabled: bool
    """Whether sending e-mail is enabled."""
    ftp_enabled: bool
    """Whether publishing reports over FTP is enabled."""
    notifications_enabled: bool
    """Whether push notifications are enabled."""
    mqid: bool
    """Whether an MetaQuotes ID is set."""
    build: int
    """Terminal build number."""
    maxbars: int
    """Maximum number of bars shown on a chart."""
    codepage: int
    """Code page of the terminal language."""
    ping_last: int
    """Last ping to the trade server in microseconds."""
    community_balance: float
    """Balance on the MQL5.community account."""
    retransmission: float
    """Percentage of lost network packets."""
    company: str
    """Company that publishes the terminal."""
    name: str
    """Terminal name."""
    language: str
    """Terminal language."""
    path: str
    """Folder the terminal is installed in."""
    data_path: str
    """Folder holding the terminal's data."""
    commondata_path: str
    """Folder shared by all terminals of this user."""


class AccountInfo(NamedTuple):
    """Trade account state, returned by account_info()."""

    login: int
    """Account number."""
    trade_mode: int
    """Account type: ACCOUNT_TRADE_MODE_DEMO, _CONTEST or _REAL."""
    leverage: int
    """Account leverage."""
    limit_orders: int
    """Maximum number of active pending orders; 0 means no limit."""
    margin_so_mode: int
    """Stop-out mode: ACCOUNT_STOPOUT_MODE_PERCENT or _MONEY."""
    trade_allowed: bool
    """Whether trading is allowed for this account."""
    trade_expert: bool
    """Whether expert advisors may trade on this account."""
    margin_mode: int
    """Margin calculation mode: ACCOUNT_MARGIN_MODE_*."""
    currency_digits: int
    """Number of decimal places of the account currency."""
    fifo_close: bool
    """Whether positions may only be closed by the FIFO rule."""
    balance: float
    """Balance in the account currency."""
    credit: float
    """Credit in the account currency."""
    profit: float
    """Current profit in the account currency."""
    equity: float
    """Equity in the account currency."""
    margin: float
    """Margin used."""
    margin_free: float
    """Free margin."""
    margin_level: float
    """Margin level in percent."""
    margin_so_call: float
    """Margin call level."""
    margin_so_so: float
    """Stop-out level."""
    margin_initial: float
    """Funds reserved for pending orders."""
    margin_maintenance: float
    """Funds reserved for open positions."""
    assets: float
    """Current assets."""
    liabilities: float
    """Current liabilities."""
    commission_blocked: float
    """Currently blocked commission."""
    name: str
    """Account holder name."""
    server: str
    """Trade server name."""
    currency: str
    """Account currency."""
    company: str
    """Name of the broker."""


class SymbolInfo(NamedTuple):
    """Full specification and current state of a symbol, returned by symbol_info() and symbols_get()."""

    custom: bool
    """Whether the symbol is custom (created in the terminal)."""
    chart_mode: int
    """Price type used for charts: SYMBOL_CHART_MODE_BID or _LAST."""
    select: bool
    """Whether the symbol is shown in Market Watch."""
    visible: bool
    """Whether the symbol is visible in Market Watch."""
    session_deals: int
    """Number of deals in the current session."""
    session_buy_orders: int
    """Number of buy orders at the moment."""
    session_sell_orders: int
    """Number of sell orders at the moment."""
    volume: int
    """Volume of the last deal."""
    volumehigh: int
    """Highest volume of the day."""
    volumelow: int
    """Lowest volume of the day."""
    time: int
    """Time of the last quote (Unix seconds)."""
    digits: int
    """Number of decimal places of the price."""
    spread: int
    """Spread in points."""
    spread_float: bool
    """Whether the spread is floating."""
    ticks_bookdepth: int
    """Maximum number of market depth requests."""
    trade_calc_mode: int
    """Contract price calculation mode: SYMBOL_CALC_MODE_*."""
    trade_mode: int
    """Order execution permission: SYMBOL_TRADE_MODE_*."""
    start_time: int
    """Date the trading starts (futures)."""
    expiration_time: int
    """Date the trading ends (futures)."""
    trade_stops_level: int
    """Minimal distance in points from the price for stop orders."""
    trade_freeze_level: int
    """Distance in points inside which orders cannot be modified."""
    trade_exemode: int
    """Execution mode: SYMBOL_TRADE_EXECUTION_*."""
    swap_mode: int
    """Swap calculation mode: SYMBOL_SWAP_MODE_*."""
    swap_rollover3days: int
    """Day of the week the triple swap is charged (DAY_OF_WEEK_*)."""
    margin_hedged_use_leg: bool
    """Whether hedged margin is calculated from the larger leg."""
    expiration_mode: int
    """Allowed order expiration modes (flags)."""
    filling_mode: int
    """Allowed order filling modes (flags)."""
    order_mode: int
    """Allowed order types (flags)."""
    order_gtc_mode: int
    """Behaviour of good-till-cancelled orders: SYMBOL_ORDERS_*."""
    option_mode: int
    """Option type: SYMBOL_OPTION_MODE_*."""
    option_right: int
    """Option right: SYMBOL_OPTION_RIGHT_CALL or _PUT."""
    bid: float
    """Current bid price."""
    bidhigh: float
    """Highest bid of the day."""
    bidlow: float
    """Lowest bid of the day."""
    ask: float
    """Current ask price."""
    askhigh: float
    """Highest ask of the day."""
    asklow: float
    """Lowest ask of the day."""
    last: float
    """Price of the last deal."""
    lasthigh: float
    """Highest last price of the day."""
    lastlow: float
    """Lowest last price of the day."""
    volume_real: float
    """Volume of the last deal with decimals."""
    volumehigh_real: float
    """Highest volume of the day with decimals."""
    volumelow_real: float
    """Lowest volume of the day with decimals."""
    option_strike: float
    """Option strike price."""
    point: float
    """Size of one point."""
    trade_tick_value: float
    """Value of one tick in the deposit currency."""
    trade_tick_value_profit: float
    """Tick value of a profitable position."""
    trade_tick_value_loss: float
    """Tick value of a losing position."""
    trade_tick_size: float
    """Minimal price change."""
    trade_contract_size: float
    """Size of one lot."""
    trade_accrued_interest: float
    """Accrued interest (bonds)."""
    trade_face_value: float
    """Face value (bonds)."""
    trade_liquidity_rate: float
    """Liquidity rate (share of the asset usable as margin)."""
    volume_min: float
    """Minimal volume of a deal."""
    volume_max: float
    """Maximal volume of a deal."""
    volume_step: float
    """Step of volume change."""
    volume_limit: float
    """Maximal total volume of positions and orders in one direction."""
    swap_long: float
    """Swap of long positions."""
    swap_short: float
    """Swap of short positions."""
    margin_initial: float
    """Initial margin per lot."""
    margin_maintenance: float
    """Maintenance margin per lot."""
    session_volume: float
    """Total volume of deals in the current session."""
    session_turnover: float
    """Total turnover of the current session."""
    session_interest: float
    """Total open interest."""
    session_buy_orders_volume: float
    """Total volume of buy orders."""
    session_sell_orders_volume: float
    """Total volume of sell orders."""
    session_open: float
    """Open price of the session."""
    session_close: float
    """Close price of the session."""
    session_aw: float
    """Average weighted price of the session."""
    session_price_settlement: float
    """Settlement price of the session."""
    session_price_limit_min: float
    """Minimal allowed price of the session."""
    session_price_limit_max: float
    """Maximal allowed price of the session."""
    margin_hedged: float
    """Contract size or margin of one lot of a hedged position."""
    price_change: float
    """Price change since the previous day, in percent."""
    price_volatility: float
    """Price volatility in percent."""
    price_theoretical: float
    """Theoretical option price."""
    price_greeks_delta: float
    """Option delta."""
    price_greeks_theta: float
    """Option theta."""
    price_greeks_gamma: float
    """Option gamma."""
    price_greeks_vega: float
    """Option vega."""
    price_greeks_rho: float
    """Option rho."""
    price_greeks_omega: float
    """Option omega."""
    price_sensitivity: float
    """Option sensitivity."""
    basis: str
    """Name of the underlying asset."""
    category: str
    """Symbol category."""
    currency_base: str
    """Base currency."""
    currency_profit: str
    """Profit currency."""
    currency_margin: str
    """Margin currency."""
    bank: str
    """Source of the current quote."""
    description: str
    """Symbol description."""
    exchange: str
    """Exchange the symbol is traded on."""
    formula: str
    """Formula of a custom symbol."""
    isin: str
    """ISIN code."""
    name: str
    """Symbol name."""
    page: str
    """Web page with information about the symbol."""
    path: str
    """Path in the symbol tree."""


class Tick(NamedTuple):
    """A price tick, returned by symbol_info_tick()."""

    time: int
    """Time of the last price update (Unix seconds)."""
    bid: float
    """Current bid price."""
    ask: float
    """Current ask price."""
    last: float
    """Price of the last deal."""
    volume: int
    """Volume of the last deal."""
    time_msc: int
    """Time of the last price update in milliseconds."""
    flags: int
    """TICK_FLAG_* bits describing what changed."""
    volume_real: float
    """Volume of the last deal with decimals."""


class BookInfo(NamedTuple):
    """One market depth entry, returned by market_book_get()."""

    type: int
    """BOOK_TYPE_SELL, BOOK_TYPE_BUY, BOOK_TYPE_SELL_MARKET or BOOK_TYPE_BUY_MARKET."""
    price: float
    """Price of the entry."""
    volume: int
    """Volume of the entry."""
    volume_dbl: float
    """Volume of the entry with decimals."""


class TradeRequest(NamedTuple):
    """A trade request, the structure passed to order_check() and order_send() (usually given as a dict)."""

    action: int
    """Kind of action: TRADE_ACTION_*."""
    magic: int
    """Expert advisor id (magic number)."""
    order: int
    """Order ticket, for modifications."""
    symbol: str
    """Symbol name."""
    volume: float
    """Requested volume in lots."""
    price: float
    """Price the order is to be executed at."""
    stoplimit: float
    """Limit price for stop-limit orders."""
    sl: float
    """Stop loss price."""
    tp: float
    """Take profit price."""
    deviation: int
    """Maximal accepted deviation from the price, in points."""
    type: int
    """Order type: ORDER_TYPE_*."""
    type_filling: int
    """Filling type: ORDER_FILLING_*."""
    type_time: int
    """Lifetime type: ORDER_TIME_*."""
    expiration: int
    """Expiration time of a pending order."""
    comment: str
    """Order comment."""
    position: int
    """Position ticket, to close or modify a position."""
    position_by: int
    """Ticket of the opposite position, for close-by."""


class OrderCheckResult(NamedTuple):
    """Outcome of order_check()."""

    retcode: int
    """Return code: TRADE_RETCODE_*."""
    balance: float
    """Balance after the deal."""
    equity: float
    """Equity after the deal."""
    profit: float
    """Floating profit."""
    margin: float
    """Margin required."""
    margin_free: float
    """Free margin left."""
    margin_level: float
    """Margin level after the deal."""
    comment: str
    """Description of the return code."""
    request: TradeRequest
    """The request that was checked."""


class OrderSendResult(NamedTuple):
    """Outcome of order_send()."""

    retcode: int
    """Return code: TRADE_RETCODE_*."""
    deal: int
    """Deal ticket, when a deal was made."""
    order: int
    """Order ticket, when an order was placed."""
    volume: float
    """Volume confirmed by the broker."""
    price: float
    """Price confirmed by the broker."""
    bid: float
    """Current bid."""
    ask: float
    """Current ask."""
    comment: str
    """Broker comment or description of the return code."""
    request_id: int
    """Request id set by the terminal."""
    retcode_external: int
    """Return code of an external trading system."""
    request: TradeRequest
    """The request that was sent."""


class TradeOrder(NamedTuple):
    """An active or historical order, returned by orders_get() and history_orders_get()."""

    ticket: int
    """Order ticket."""
    time_setup: int
    """Time the order was placed (Unix seconds)."""
    time_setup_msc: int
    """Time the order was placed in milliseconds."""
    time_done: int
    """Time the order was executed or cancelled."""
    time_done_msc: int
    """Execution or cancellation time in milliseconds."""
    time_expiration: int
    """Expiration time of the order."""
    type: int
    """Order type: ORDER_TYPE_*."""
    type_time: int
    """Lifetime type: ORDER_TIME_*."""
    type_filling: int
    """Filling type: ORDER_FILLING_*."""
    state: int
    """Order state: ORDER_STATE_*."""
    magic: int
    """Expert advisor id (magic number)."""
    position_id: int
    """Id of the position the order belongs to."""
    position_by_id: int
    """Id of the opposite position, for close-by."""
    reason: int
    """Reason the order was placed: ORDER_REASON_*."""
    volume_current: float
    """Unfilled volume."""
    volume_initial: float
    """Original volume."""
    price_open: float
    """Order price."""
    price_stoplimit: float
    """Limit price of a stop-limit order."""
    sl: float
    """Stop loss price."""
    tp: float
    """Take profit price."""
    price_current: float
    """Current price of the symbol."""
    symbol: str
    """Symbol name."""
    comment: str
    """Order comment."""
    external_id: str
    """Order id in an external trading system."""


class TradePosition(NamedTuple):
    """An open position, returned by positions_get()."""

    ticket: int
    """Position ticket."""
    time: int
    """Time the position was opened (Unix seconds)."""
    time_msc: int
    """Opening time in milliseconds."""
    time_update: int
    """Time of the last change."""
    time_update_msc: int
    """Time of the last change in milliseconds."""
    type: int
    """POSITION_TYPE_BUY or POSITION_TYPE_SELL."""
    magic: int
    """Expert advisor id (magic number)."""
    identifier: int
    """Position id."""
    reason: int
    """Reason the position was opened: POSITION_REASON_*."""
    volume: float
    """Position volume in lots."""
    price_open: float
    """Opening price."""
    sl: float
    """Stop loss price."""
    tp: float
    """Take profit price."""
    price_current: float
    """Current price of the symbol."""
    swap: float
    """Accumulated swap."""
    profit: float
    """Current profit."""
    symbol: str
    """Symbol name."""
    comment: str
    """Position comment."""
    external_id: str
    """Position id in an external trading system."""


class TradeDeal(NamedTuple):
    """A historical deal, returned by history_deals_get()."""

    ticket: int
    """Deal ticket."""
    order: int
    """Ticket of the order the deal came from."""
    time: int
    """Time of the deal (Unix seconds)."""
    time_msc: int
    """Time of the deal in milliseconds."""
    type: int
    """Deal type: DEAL_TYPE_*."""
    entry: int
    """Direction: DEAL_ENTRY_IN, _OUT, _INOUT or _OUT_BY."""
    magic: int
    """Expert advisor id (magic number)."""
    position_id: int
    """Id of the position the deal opened or closed."""
    reason: int
    """Reason of the deal: DEAL_REASON_*."""
    volume: float
    """Deal volume in lots."""
    price: float
    """Deal price."""
    commission: float
    """Commission."""
    swap: float
    """Swap charged on closing."""
    profit: float
    """Profit of the deal."""
    fee: float
    """Fee charged after the deal."""
    symbol: str
    """Symbol name."""
    comment: str
    """Deal comment."""
    external_id: str
    """Deal id in an external trading system."""


RECORDS = {
    "TerminalInfo": TerminalInfo,
    "AccountInfo": AccountInfo,
    "SymbolInfo": SymbolInfo,
    "Tick": Tick,
    "BookInfo": BookInfo,
    "TradeRequest": TradeRequest,
    "OrderCheckResult": OrderCheckResult,
    "OrderSendResult": OrderSendResult,
    "TradeOrder": TradeOrder,
    "TradePosition": TradePosition,
    "TradeDeal": TradeDeal,
}
