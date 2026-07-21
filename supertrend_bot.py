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
    return now.weekday() < 5 and now.replace(hour=9, minute=15) <= now <= now.replace(hour=15, minute=30)

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
    # ================= INDICES =================
    "^NSEI": 10,
    "^NSEBANK": 30,

    # ================= STOCKS (UNIQUE LIST) =================
    "RELIANCE.NS": 8, "TCS.NS": 8, "HDFCBANK.NS": 8, "ICICIBANK.NS": 8,
    "INFY.NS": 8, "ITC.NS": 8, "SBIN.NS": 8, "LT.NS": 8,
    "AXISBANK.NS": 8, "KOTAKBANK.NS": 8, "BHARTIARTL.NS": 8,
    "ASIANPAINT.NS": 8, "MARUTI.NS": 8, "SUNPHARMA.NS": 8,
    "TITAN.NS": 8, "ULTRACEMCO.NS": 8, "BAJFINANCE.NS": 8,
    "HCLTECH.NS": 8, "WIPRO.NS": 8, "POWERGRID.NS": 8,
    "NTPC.NS": 8, "ONGC.NS": 8, "COALINDIA.NS": 8,
    "JSWSTEEL.NS": 8, "TATASTEEL.NS": 8, "HINDALCO.NS": 8,
    "GRASIM.NS": 8, "ADANIENT.NS": 8, "ADANIPORTS.NS": 8,
    "BAJAJFINSV.NS": 8, "BAJAJ-AUTO.NS": 8, "EICHERMOT.NS": 8,
    "HEROMOTOCO.NS": 8, "BRITANNIA.NS": 8, "NESTLEIND.NS": 8,
    "HINDUNILVR.NS": 8, "DABUR.NS": 8, "DIVISLAB.NS": 8,
    "DRREDDY.NS": 8, "CIPLA.NS": 8, "APOLLOHOSP.NS": 8,
    "INDUSINDBK.NS": 8, "SBILIFE.NS": 8, "HDFCLIFE.NS": 8,
    "ICICIPRULI.NS": 8, "UPL.NS": 8, "TECHM.NS": 8,
    "BANKBARODA.NS": 8, "PNB.NS": 8, "FEDERALBNK.NS": 8,
    "IDFCFIRSTB.NS": 8, "AUBANK.NS": 8, "BANDHANBNK.NS": 8
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

            prev_close = close.iloc[-2]
            prev_st = st.iloc[-2]

            current_price = close.iloc[-1]
            diff = abs(current_price - prev_st)

            if symbol in open_trades:
                continue

            # ================= BUY =================
            if prev_close > prev_st and current_price < prev_close:
                if diff <= threshold:
                    open_trades[symbol] = {
                        "type": "BUY",
                        "entry": current_price,
                        "sl": prev_st
                    }

                    send_telegram(f"""
🟢 BUY (CALL)
{symbol}
Entry: {round(current_price,2)}
ST: {round(prev_st,2)}
Diff: {round(diff,2)}
""")

            # ================= SELL =================
            elif prev_close < prev_st and current_price > prev_close:
                if diff <= threshold:
                    open_trades[symbol] = {
                        "type": "SELL",
                        "entry": current_price,
                        "sl": prev_st
                    }

                    send_telegram(f"""
🔴 SELL (PUT)
{symbol}
Entry: {round(current_price,2)}
ST: {round(prev_st,2)}
Diff: {round(diff,2)}
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

            prev_close = close.iloc[-2]
            prev_st = st.iloc[-2]

            trade = open_trades[symbol]
            entry = trade["entry"]

            if trade["type"] == "BUY":

                if prev_close < prev_st:
                    pnl = prev_close - entry
                    send_telegram(f"❌ SL BUY {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"BUY",entry,prev_st,prev_close,pnl,"SL")
                    del open_trades[symbol]

                elif prev_close >= entry * 1.10:
                    pnl = prev_close - entry
                    send_telegram(f"✅ TARGET BUY {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"BUY",entry,prev_st,prev_close,pnl,"TARGET")
                    del open_trades[symbol]

            else:

                if prev_close > prev_st:
                    pnl = entry - prev_close
                    send_telegram(f"❌ SL SELL {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"SELL",entry,prev_st,prev_close,pnl,"SL")
                    del open_trades[symbol]

                elif prev_close <= entry * 0.90:
                    pnl = entry - prev_close
                    send_telegram(f"✅ TARGET SELL {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"SELL",entry,prev_st,prev_close,pnl,"TARGET")
                    del open_trades[symbol]

        except Exception as e:
            print("EXIT ERROR:", e)

# ================= MAIN =================
print("🚀 SUPER TREND BOT STARTED")
send_telegram("✅ SUPER TREND BOT LIVE")

init_csv()

while True:
    try:
        if is_market_open():

            run_bot()
            check_exit()

            time.sleep(8)   # LIVE monitoring

        else:
            time.sleep(20)

    except Exception as e:
        print("MAIN ERROR:", e)
        time.sleep(10)
