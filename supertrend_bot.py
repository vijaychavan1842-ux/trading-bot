import yfinance as yf
import pandas as pd
import numpy as np
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

        requests.post(url, json={
            "chat_id": chat_id,
            "text": msg
        }, timeout=10)

    except Exception as e:
        print("Telegram Error:", e)

# ================= TIME =================
india = pytz.timezone('Asia/Kolkata')

def now_ist():
    return datetime.now(india)

def is_market_open():
    now = now_ist()
    if now.weekday() >= 5:
        return False
    return now.replace(hour=9, minute=15) <= now <= now.replace(hour=15, minute=30)

def is_candle_close():
    now = now_ist()
    return now.minute % 5 == 0 and now.second < 8

# ================= SUPER TREND =================
def supertrend(df, period=7, multiplier=3):
    hl2 = (df['High'] + df['Low']) / 2
    atr = df['High'].rolling(period).max() - df['Low'].rolling(period).min()

    upperband = hl2 + (multiplier * atr)
    lowerband = hl2 - (multiplier * atr)

    final_upper = upperband.copy()
    final_lower = lowerband.copy()

    for i in range(1, len(df)):
        if df['Close'][i-1] <= final_upper[i-1]:
            final_upper[i] = min(upperband[i], final_upper[i-1])
        else:
            final_upper[i] = upperband[i]

        if df['Close'][i-1] >= final_lower[i-1]:
            final_lower[i] = max(lowerband[i], final_lower[i-1])
        else:
            final_lower[i] = lowerband[i]

    st = pd.Series(index=df.index)

    for i in range(len(df)):
        if df['Close'][i] <= final_upper[i]:
            st[i] = final_upper[i]
        else:
            st[i] = final_lower[i]

    return st

# ================= SYMBOLS =================
symbols = {
    "^NSEI": 10,
    "^NSEBANK": 20
}

open_trades = {}

# ================= CSV =================
def init_csv():
    if not os.path.exists("st_trade_log.csv"):
        with open("st_trade_log.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Time","Index","Type","Entry","SL","Exit","PnL","Reason"])

def log_trade(index, ttype, entry, sl, exit_price, pnl, reason):
    with open("st_trade_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now(), index, ttype,
            round(entry,2), round(sl,2),
            round(exit_price,2), round(pnl,2), reason
        ])

# ================= ATM OPTION =================
def get_atm_strike(price, step):
    return round(price / step) * step

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

            # BUY CONDITION (price near ST from above)
            if price > st_val and diff <= threshold:
                strike = get_atm_strike(price, 50)
                open_trades[symbol] = {
                    "type": "BUY",
                    "entry": price,
                    "sl": st_val,
                    "strike": strike
                }

                send_telegram(f"""
BUY SIGNAL (CALL)
Index: {symbol}
Spot: {price}
ST: {round(st_val,2)}
ATM: {strike} CE
""")

            # SELL CONDITION
            elif price < st_val and diff <= threshold:
                strike = get_atm_strike(price, 50)
                open_trades[symbol] = {
                    "type": "SELL",
                    "entry": price,
                    "sl": st_val,
                    "strike": strike
                }

                send_telegram(f"""
SELL SIGNAL (PUT)
Index: {symbol}
Spot: {price}
ST: {round(st_val,2)}
ATM: {strike} PE
""")

        except Exception as e:
            print("ENTRY ERROR:", e)

# ================= EXIT =================
def check_exit():
    for symbol in list(open_trades.keys()):
        try:
            df = yf.download(symbol, interval="5m", period="5d", progress=False).dropna()

            close = df["Close"]
            st = supertrend(df)

            price = close.iloc[-2]
            st_val = st.iloc[-2]

            trade = open_trades[symbol]
            entry = trade["entry"]
            sl = trade["sl"]

            if trade["type"] == "BUY":

                if price < st_val:
                    pnl = price - entry
                    send_telegram(f"SL BUY {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"BUY",entry,sl,price,pnl,"SL")
                    del open_trades[symbol]

                elif price >= entry * 1.10:
                    pnl = price - entry
                    send_telegram(f"TARGET BUY {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"BUY",entry,sl,price,pnl,"TARGET")
                    del open_trades[symbol]

            else:

                if price > st_val:
                    pnl = entry - price
                    send_telegram(f"SL SELL {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"SELL",entry,sl,price,pnl,"SL")
                    del open_trades[symbol]

                elif price <= entry * 0.90:
                    pnl = entry - price
                    send_telegram(f"TARGET SELL {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"SELL",entry,sl,price,pnl,"TARGET")
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
        now = now_ist()

        if is_market_open() and is_candle_close():

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
