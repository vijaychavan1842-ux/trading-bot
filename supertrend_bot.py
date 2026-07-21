import yfinance as yf
import pandas as pd
import requests
import time
import csv
from datetime import datetime
import pytz
import os

# ================= TELEGRAM =================
def send_telegram(msg):
    try:
        token = str(os.getenv("TOKEN")).strip()
        chat_id = str(os.getenv("CHAT_ID")).strip()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": msg}, timeout=10)
    except Exception as e:
        print("Telegram Error:", e)

# ================= TIME =================
india = pytz.timezone('Asia/Kolkata')

def now_ist():
    return datetime.now(india)

def is_market_open():
    now = now_ist()
    return now.weekday() < 5 and now.replace(hour=9, minute=15) <= now <= now.replace(hour=23, minute=30)

# ================= SUPER TREND =================
def supertrend(df, period=7, multiplier=3):
    hl2 = (df['High'] + df['Low']) / 2
    atr = df['High'].rolling(period).max() - df['Low'].rolling(period).min()
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr

    st = pd.Series(index=df.index)

    for i in range(len(df)):
        if df['Close'][i] > upper[i]:
            st[i] = lower[i]
        else:
            st[i] = upper[i]

    return st

# ================= SYMBOLS =================
symbols = {
    "^NSEI": 15,
    "^NSEBANK": 80,

    # STOCKS
    "RELIANCE.NS": 8, "TCS.NS": 8, "HDFCBANK.NS": 8, "ICICIBANK.NS": 8,
    "INFY.NS": 8, "ITC.NS": 8, "SBIN.NS": 8, "LT.NS": 8,

    # COMMODITY (Yahoo symbols)
    "GC=F": 10,   # GOLD
    "SI=F": 5,    # SILVER
    "CL=F": 1     # CRUDE
}

open_trades = {}

# ================= CSV =================
def init_csv():
    if not os.path.exists("trade_log_day.csv"):
        with open("trade_log_day.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Time","Symbol","Type","Entry","SL","Exit","PnL","Reason"])

def log_trade(symbol, ttype, entry, sl, exit_price, pnl, reason):
    with open("trade_log_day.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now(), symbol, ttype, entry, sl, exit_price, pnl, reason])

# ================= ENTRY =================
def run_bot():
    for symbol, threshold in symbols.items():
        try:
            df = yf.download(symbol, interval="5m", period="2d", progress=False).dropna()

            close = df["Close"]
            st = supertrend(df)

            prev_close = close.iloc[-2]
            prev_st = st.iloc[-2]

            # ✅ REAL CMP (LIVE)
            ticker = yf.Ticker(symbol)
            current_price = ticker.history(period="1d", interval="1m")["Close"].iloc[-1]

            diff = abs(current_price - prev_st)

            if symbol in open_trades:
                continue

            # ================= ENTRY (NO DIRECTION CONDITION) =================
            if diff <= threshold:

                trade_type = "BUY" if prev_close > prev_st else "SELL"

                open_trades[symbol] = {
                    "type": trade_type,
                    "entry": current_price,
                    "sl": prev_st
                }

                send_telegram(f"""
━━━━━━━━━━━━━━━
🔥 ENTRY SIGNAL

Symbol: {symbol}
Type: {trade_type}
Entry: {round(current_price,2)}
ST: {round(prev_st,2)}
Diff: {round(diff,2)}

━━━━━━━━━━━━━━━
""")

        except Exception as e:
            print("ENTRY ERROR:", e)

# ================= EXIT =================
def check_exit():
    for symbol in list(open_trades.keys()):
        try:
            df = yf.download(symbol, interval="5m", period="2d", progress=False).dropna()

            close = df["Close"]
            st = supertrend(df)

            prev_close = close.iloc[-2]
            prev_st = st.iloc[-2]

            ticker = yf.Ticker(symbol)
            current_price = ticker.history(period="1d", interval="1m")["Close"].iloc[-1]

            trade = open_trades[symbol]
            entry = trade["entry"]

            # ================= SL (CANDLE CLOSE BASED) =================
            if trade["type"] == "BUY" and prev_close < prev_st:
                pnl = current_price - entry
                send_telegram(f"❌ SL BUY {symbol} PnL:{round(pnl,2)}")
                log_trade(symbol,"BUY",entry,prev_st,current_price,pnl,"SL")
                del open_trades[symbol]

            elif trade["type"] == "SELL" and prev_close > prev_st:
                pnl = entry - current_price
                send_telegram(f"❌ SL SELL {symbol} PnL:{round(pnl,2)}")
                log_trade(symbol,"SELL",entry,prev_st,current_price,pnl,"SL")
                del open_trades[symbol]

            # ================= TARGET (CMP BASED) =================
            elif trade["type"] == "BUY" and current_price >= entry * 1.10:
                pnl = current_price - entry
                send_telegram(f"🎯 TARGET BUY {symbol} PnL:{round(pnl,2)}")
                log_trade(symbol,"BUY",entry,prev_st,current_price,pnl,"TARGET")
                del open_trades[symbol]

            elif trade["type"] == "SELL" and current_price <= entry * 0.90:
                pnl = entry - current_price
                send_telegram(f"🎯 TARGET SELL {symbol} PnL:{round(pnl,2)}")
                log_trade(symbol,"SELL",entry,prev_st,current_price,pnl,"TARGET")
                del open_trades[symbol]

        except Exception as e:
            print("EXIT ERROR:", e)

# ================= CSV EXPORT =================
def export_csv():
    now = now_ist()

    if now.hour == 15 and now.minute == 35:
        os.rename("trade_log_day.csv", f"trade_log_335_{now.date()}.csv")

    if now.hour == 23 and now.minute == 5:
        os.rename("trade_log_day.csv", f"trade_log_1105_{now.date()}.csv")

# ================= MAIN =================
print("🚀 BOT STARTED")
send_telegram("✅ BOT LIVE")

init_csv()

while True:
    try:
        if is_market_open():

            run_bot()
            check_exit()
            export_csv()

            time.sleep(5)   # FAST CHECK (LIVE CMP)

        else:
            time.sleep(20)

    except Exception as e:
        print("MAIN ERROR:", e)
        time.sleep(10)
