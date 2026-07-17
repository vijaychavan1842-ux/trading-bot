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
    token = str(os.getenv("TOKEN")).strip()
    chat_id = str(os.getenv("CHAT_ID")).strip()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": msg}, timeout=10)

# ================= TIME =================
india = pytz.timezone('Asia/Kolkata')

def now_ist():
    return datetime.now(india)

def is_market_open():
    now = now_ist()
    return now.weekday() < 5 and now.replace(hour=9, minute=15) <= now <= now.replace(hour=15, minute=30)

def is_candle_close():
    now = now_ist()
    return now.minute % 5 == 0 and now.second < 8

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
    "^NSEI": 10,
    "^NSEBANK": 20,
    "RELIANCE.NS": 5,"TCS.NS": 5,"HDFCBANK.NS": 5,"ICICIBANK.NS": 5,
    "INFY.NS": 5,"ITC.NS": 5,"SBIN.NS": 5,"LT.NS": 5,
    "AXISBANK.NS": 5,"KOTAKBANK.NS": 5
}

open_trades = {}

# ================= CSV =================
def init_csv():
    if not os.path.exists("st_trade_log.csv"):
        with open("st_trade_log.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Time","Symbol","Type","Entry","SL","Exit","PnL","Reason"])

def log_trade(symbol, ttype, entry, sl, exit_price, pnl, reason):
    with open("st_trade_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now(), symbol, ttype, entry, sl, exit_price, pnl, reason])

# ================= ENTRY =================
def run_bot():
    for symbol, threshold in symbols.items():
        try:
            df = yf.download(symbol, interval="5m", period="5d", progress=False).dropna()

            close = df["Close"]
            st = supertrend(df)

            price = close.iloc[-2]
            st_val = st.iloc[-2]

            diff = abs(price - st_val)

            if symbol in open_trades:
                continue

            # BUY
            if price > st_val and diff <= threshold:
                open_trades[symbol] = {"type":"BUY","entry":price,"sl":st_val}
                send_telegram(f"BUY {symbol}\nEntry:{price}\nST:{round(st_val,2)}")

            # SELL
            elif price < st_val and diff <= threshold:
                open_trades[symbol] = {"type":"SELL","entry":price,"sl":st_val}
                send_telegram(f"SELL {symbol}\nEntry:{price}\nST:{round(st_val,2)}")

        except Exception as e:
            print("ENTRY ERROR:", e)

# ================= EXIT =================
def check_exit():
    for symbol in list(open_trades.keys()):
        try:
            df = yf.download(symbol, interval="5m", period="5d", progress=False).dropna()

            close = df["Close"]
            st = supertrend(df)

            prev_close = close.iloc[-2]
            prev_st = st.iloc[-2]

            trade = open_trades[symbol]
            entry = trade["entry"]

            if trade["type"] == "BUY":

                if prev_close < prev_st:
                    pnl = prev_close - entry
                    send_telegram(f"SL BUY {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"BUY",entry,prev_st,prev_close,pnl,"SL")
                    del open_trades[symbol]

                elif prev_close >= entry * 1.10:
                    pnl = prev_close - entry
                    send_telegram(f"TARGET BUY {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"BUY",entry,prev_st,prev_close,pnl,"TARGET")
                    del open_trades[symbol]

            else:

                if prev_close > prev_st:
                    pnl = entry - prev_close
                    send_telegram(f"SL SELL {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"SELL",entry,prev_st,prev_close,pnl,"SL")
                    del open_trades[symbol]

                elif prev_close <= entry * 0.90:
                    pnl = entry - prev_close
                    send_telegram(f"TARGET SELL {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"SELL",entry,prev_st,prev_close,pnl,"TARGET")
                    del open_trades[symbol]

        except Exception as e:
            print("EXIT ERROR:", e)

# ================= MAIN =================
print("🚀 SUPER TREND BOT STARTED")
send_telegram("✅ SUPER TREND BOT LIVE")

init_csv()

last_run = None

while True:
    try:
        if is_market_open() and is_candle_close():

            now = now_ist()

            if last_run != now.minute:
                run_bot()
                check_exit()
                last_run = now.minute

            time.sleep(5)
        else:
            time.sleep(20)

    except Exception as e:
        print("MAIN ERROR:", e)
        time.sleep(10)
