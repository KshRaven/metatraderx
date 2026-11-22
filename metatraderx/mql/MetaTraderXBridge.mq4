//+------------------------------------------------------------------+
//| MetaTraderXBridge.mq4 - read-only data bridge for MetaTraderX    |
//| Attach to any chart with "Allow DLL imports" enabled.            |
//+------------------------------------------------------------------+
#property strict
#property version "1.00"

#import "ws2_32.dll"
int WSAStartup(int version, uchar &data[]);
int WSACleanup();
int WSAGetLastError();
int socket(int af, int type, int proto);
int connect(int s, uchar &addr[], int len);
int closesocket(int s);
int send(int s, uchar &buf[], int len, int flags);
int recv(int s, uchar &buf[], int len, int flags);
int ioctlsocket(int s, int cmd, int &arg);
#import

#define FIONBIO_CMD (-2147195266)
#define WOULDBLOCK  10035

input string Host = "127.0.0.1";
input int    Port = 5555;

int    sock = INVALID_HANDLE;
bool   wsa  = false;
string acc  = "";
uint   lastTry = 0;

int OnInit()
{
   uchar d[512];
   wsa = (WSAStartup(0x0202, d) == 0);
   if(!wsa) { Print("WSAStartup failed; enable Allow DLL imports"); return INIT_FAILED; }
   EventSetMillisecondTimer(10);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Drop();
   if(wsa) WSACleanup();
}

void Drop()
{
   if(sock != INVALID_HANDLE) closesocket(sock);
   sock = INVALID_HANDLE;
   acc = "";
}

string Q(string s)
{
   StringReplace(s, "\\", "\\\\");
   StringReplace(s, "\"", "\\\"");
   StringReplace(s, "\n", " ");
   StringReplace(s, "\r", " ");
   return "\"" + s + "\"";
}

string D(double v) { return DoubleToString(v, 8); }
string L(long v)   { return IntegerToString(v); }
string B(bool v)   { return v ? "true" : "false"; }

void Send(string s)
{
   uchar b[];
   int n = StringToCharArray(s + "\n", b, 0, WHOLE_ARRAY, CP_UTF8) - 1;
   int sent = 0;
   int waits = 0;
   while(n > 0 && sent < n)
   {
      int m = n - sent;
      if(m > 65536) m = 65536;
      uchar part[];
      ArrayResize(part, m);
      ArrayCopy(part, b, 0, sent, m);
      int r = send(sock, part, m, 0);
      if(r < 0 && WSAGetLastError() == WOULDBLOCK) { Sleep(1); if(++waits > 5000) { Drop(); return; } continue; }
      if(r <= 0) { Drop(); return; }
      sent += r;
   }
}

string SymJson(string s)
{
   if(!SymbolSelect(s, true)) { }
   return "{\"name\":" + Q(s)
      + ",\"description\":" + Q(SymbolInfoString(s, SYMBOL_DESCRIPTION))
      + ",\"path\":" + Q(SymbolInfoString(s, SYMBOL_PATH))
      + ",\"currency_base\":" + Q(SymbolInfoString(s, SYMBOL_CURRENCY_BASE))
      + ",\"currency_profit\":" + Q(SymbolInfoString(s, SYMBOL_CURRENCY_PROFIT))
      + ",\"currency_margin\":" + Q(SymbolInfoString(s, SYMBOL_CURRENCY_MARGIN))
      + ",\"digits\":" + L(SymbolInfoInteger(s, SYMBOL_DIGITS))
      + ",\"spread\":" + L(SymbolInfoInteger(s, SYMBOL_SPREAD))
      + ",\"select\":" + B(SymbolInfoInteger(s, SYMBOL_SELECT) != 0)
      + ",\"visible\":" + B(SymbolInfoInteger(s, SYMBOL_VISIBLE) != 0)
      + ",\"trade_mode\":" + L(SymbolInfoInteger(s, SYMBOL_TRADE_MODE))
      + ",\"trade_stops_level\":" + L(SymbolInfoInteger(s, SYMBOL_TRADE_STOPS_LEVEL))
      + ",\"trade_freeze_level\":" + L(SymbolInfoInteger(s, SYMBOL_TRADE_FREEZE_LEVEL))
      + ",\"point\":" + D(SymbolInfoDouble(s, SYMBOL_POINT))
      + ",\"bid\":" + D(SymbolInfoDouble(s, SYMBOL_BID))
      + ",\"ask\":" + D(SymbolInfoDouble(s, SYMBOL_ASK))
      + ",\"trade_tick_size\":" + D(SymbolInfoDouble(s, SYMBOL_TRADE_TICK_SIZE))
      + ",\"trade_tick_value\":" + D(SymbolInfoDouble(s, SYMBOL_TRADE_TICK_VALUE))
      + ",\"trade_contract_size\":" + D(SymbolInfoDouble(s, SYMBOL_TRADE_CONTRACT_SIZE))
      + ",\"volume_min\":" + D(SymbolInfoDouble(s, SYMBOL_VOLUME_MIN))
      + ",\"volume_max\":" + D(SymbolInfoDouble(s, SYMBOL_VOLUME_MAX))
      + ",\"volume_step\":" + D(SymbolInfoDouble(s, SYMBOL_VOLUME_STEP))
      + ",\"swap_long\":" + D(SymbolInfoDouble(s, SYMBOL_SWAP_LONG))
      + ",\"swap_short\":" + D(SymbolInfoDouble(s, SYMBOL_SWAP_SHORT)) + "}";
}

string RatesJson(MqlRates &r[], int n)
{
   string o = "[";
   for(int i = 0; i < n; i++)
   {
      if(i > 0) o += ",";
      o += "[" + L((long)r[i].time) + "," + D(r[i].open) + "," + D(r[i].high) + "," + D(r[i].low) + "," + D(r[i].close)
         + "," + L(r[i].tick_volume) + "," + IntegerToString(r[i].spread) + "," + L(r[i].real_volume) + "]";
   }
   return o + "]";
}

string TradesJson(bool history, datetime from, datetime to)
{
   string o = "[";
   int total = history ? OrdersHistoryTotal() : OrdersTotal();
   bool first = true;
   for(int i = 0; i < total; i++)
   {
      if(!OrderSelect(i, SELECT_BY_POS, history ? MODE_HISTORY : MODE_TRADES)) continue;
      if(history && (OrderCloseTime() < from || OrderCloseTime() > to)) continue;
      if(!first) o += ",";
      first = false;
      o += "{\"ticket\":" + L(OrderTicket()) + ",\"open_time\":" + L((long)OrderOpenTime()) + ",\"close_time\":" + L((long)OrderCloseTime())
         + ",\"type\":" + IntegerToString(OrderType()) + ",\"volume\":" + D(OrderLots()) + ",\"symbol\":" + Q(OrderSymbol())
         + ",\"open_price\":" + D(OrderOpenPrice()) + ",\"close_price\":" + D(OrderClosePrice())
         + ",\"sl\":" + D(OrderStopLoss()) + ",\"tp\":" + D(OrderTakeProfit())
         + ",\"commission\":" + D(OrderCommission()) + ",\"swap\":" + D(OrderSwap()) + ",\"profit\":" + D(OrderProfit())
         + ",\"magic\":" + IntegerToString(OrderMagicNumber()) + ",\"comment\":" + Q(OrderComment()) + "}";
   }
   return o + "]";
}

string Dispatch(string m, string &a[], int na)
{
   if(m == "ping") return "true";
   if(m == "account_info")
   {
      double mg = AccountMargin();
      return "{\"login\":" + L(AccountNumber()) + ",\"trade_mode\":" + L(AccountInfoInteger(ACCOUNT_TRADE_MODE))
         + ",\"leverage\":" + L(AccountLeverage()) + ",\"limit_orders\":" + L(AccountInfoInteger(ACCOUNT_LIMIT_ORDERS))
         + ",\"margin_so_mode\":" + L(AccountStopoutMode()) + ",\"trade_allowed\":" + B(IsTradeAllowed())
         + ",\"trade_expert\":" + B(IsExpertEnabled()) + ",\"balance\":" + D(AccountBalance()) + ",\"credit\":" + D(AccountCredit())
         + ",\"profit\":" + D(AccountProfit()) + ",\"equity\":" + D(AccountEquity()) + ",\"margin\":" + D(mg)
         + ",\"margin_free\":" + D(AccountFreeMargin()) + ",\"margin_level\":" + D(mg > 0 ? AccountEquity() / mg * 100.0 : 0.0)
         + ",\"margin_so_call\":" + D(AccountStopoutLevel()) + ",\"margin_so_so\":" + D(AccountStopoutLevel())
         + ",\"name\":" + Q(AccountName()) + ",\"server\":" + Q(AccountServer()) + ",\"currency\":" + Q(AccountCurrency())
         + ",\"company\":" + Q(AccountCompany()) + "}";
   }
   if(m == "terminal_info")
      return "{\"connected\":" + B(IsConnected()) + ",\"trade_allowed\":" + B(IsTradeAllowed())
         + ",\"dlls_allowed\":" + B(IsDllsAllowed()) + ",\"build\":" + L(TerminalInfoInteger(TERMINAL_BUILD))
         + ",\"maxbars\":" + L(TerminalInfoInteger(TERMINAL_MAXBARS)) + ",\"company\":" + Q(TerminalCompany())
         + ",\"name\":" + Q(TerminalName()) + ",\"path\":" + Q(TerminalPath()) + ",\"data_path\":" + Q(TerminalInfoString(TERMINAL_DATA_PATH))
         + ",\"commondata_path\":" + Q(TerminalInfoString(TERMINAL_COMMONDATA_PATH)) + "}";
   if(m == "symbols")
   {
      bool sel = (na > 0 && a[0] == "1");
      string o = "[";
      int n = SymbolsTotal(sel);
      for(int i = 0; i < n; i++)
      {
         if(i > 0) o += ",";
         o += SymJson(SymbolName(i, sel));
      }
      return o + "]";
   }
   if(m == "symbol_info" && na > 0) return SymbolInfoInteger(a[0], SYMBOL_DIGITS) > 0 || SymbolSelect(a[0], true) ? SymJson(a[0]) : "null";
   if(m == "tick" && na > 0)
   {
      MqlTick t;
      if(!SymbolInfoTick(a[0], t)) return "null";
      return "{\"time\":" + L((long)t.time) + ",\"bid\":" + D(t.bid) + ",\"ask\":" + D(t.ask) + ",\"last\":" + D(t.last)
         + ",\"volume\":" + L((long)t.volume) + ",\"time_msc\":" + L((long)t.time * 1000) + ",\"flags\":6,\"volume_real\":0}";
   }
   if(m == "symbol_select" && na > 1) return B(SymbolSelect(a[0], a[1] == "1"));
   if(m == "rates_pos" && na > 3)
   {
      MqlRates r[];
      int n = CopyRates(a[0], (ENUM_TIMEFRAMES)StringToInteger(a[1]), (int)StringToInteger(a[2]), (int)StringToInteger(a[3]), r);
      return n > 0 ? RatesJson(r, n) : "null";
   }
   if(m == "rates_range" && na > 3)
   {
      MqlRates r[];
      int n = CopyRates(a[0], (ENUM_TIMEFRAMES)StringToInteger(a[1]), (datetime)StringToInteger(a[2]), (datetime)StringToInteger(a[3]), r);
      return n > 0 ? RatesJson(r, n) : "null";
   }
   if(m == "open_trades") return TradesJson(false, 0, 0);
   if(m == "history" && na > 1) return TradesJson(true, (datetime)StringToInteger(a[0]), (datetime)StringToInteger(a[1]));
   return "";
}

void Handle(string line)
{
   string p[];
   int n = StringSplit(line, '|', p);
   if(n < 2) return;
   string a[];
   ArrayResize(a, n - 2);
   for(int i = 2; i < n; i++) a[i - 2] = p[i];
   ResetLastError();
   string r = Dispatch(p[1], a, n - 2);
   if(r == "")
      Send("{\"id\":" + p[0] + ",\"ok\":false,\"e\":" + Q("unsupported " + p[1]) + "}");
   else
      Send("{\"id\":" + p[0] + ",\"ok\":true,\"r\":" + r + "}");
}

bool Open()
{
   string ip[];
   if(StringSplit(Host, '.', ip) != 4) return false;
   uchar a[16];
   ArrayInitialize(a, 0);
   a[0] = 2;
   a[2] = (uchar)(Port >> 8);
   a[3] = (uchar)(Port & 255);
   for(int i = 0; i < 4; i++) a[4 + i] = (uchar)StringToInteger(ip[i]);
   int s = socket(2, 1, 6);
   if(s == INVALID_HANDLE) return false;
   if(connect(s, a, 16) != 0) { closesocket(s); return false; }
   int one = 1;
   ioctlsocket(s, FIONBIO_CMD, one);
   sock = s;
   return true;
}

void OnTimer()
{
   if(sock == INVALID_HANDLE)
   {
      if(GetTickCount() - lastTry < 1000) return;
      lastTry = GetTickCount();
      if(!Open()) return;
   }
   uchar buf[];
   ArrayResize(buf, 65536);
   int got = recv(sock, buf, 65536, 0);
   if(got == 0) { Drop(); return; }
   if(got < 0)
   {
      if(WSAGetLastError() != WOULDBLOCK) Drop();
      return;
   }
   acc += CharArrayToString(buf, 0, got, CP_UTF8);
   int pos;
   while((pos = StringFind(acc, "\n")) >= 0)
   {
      string line = StringSubstr(acc, 0, pos);
      acc = StringSubstr(acc, pos + 1);
      if(StringLen(line) > 0) Handle(line);
   }
}
