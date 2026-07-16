import yfinance as yf
import pandas as pd
import requests
import time
import csv
from datetime import datetime
import pytz
import os

# ================= TELEGRAM =================
TOKEN = os.getenv("TO8717830004:AAEKMFUHs9mV4c0mrYalmX6zmuJ3knKcnBoKEN")
CHAT_ID = os.getenv("538248415")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg})
    except:
        print("Telegram Error")

def send_csv():
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
        files = {'document': open('trade_log.csv', 'rb')}
        data = {'chat_id': CHAT_ID}
        requests.post(url, files=files, data=data)
    except:
        print("CSV Error")

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
    return now.minute % 15 == 0 and now.second < 10

# ================= RSI =================
def rsi_tv(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ================= SYMBOLS =================
symbols = [
"RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS",
"HINDUNILVR.NS","ITC.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
"LT.NS","AXISBANK.NS","BAJFINANCE.NS","MARUTI.NS","TITAN.NS",
# BANKNIFTY
"SBIN.NS","AXISBANK.NS","ICICIBANK.NS","HDFCBANK.NS","KOTAKBANK.NS",
# INDEX
"^NSEI","^NSEBANK"
]

# ================= STORAGE =================
open_trades = {}

# ================= TRADE LOG =================
def log_trade(symbol, ttype, entry, exit_price, pnl, reason):
    with open("trade_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now(), symbol, ttype,
            round(entry,2), round(exit_price,2),
            round(pnl,2), reason
        ])

# ================= ENTRY =================
def run_bot():
    for symbol in symbols:
        try:
            df = yf.download(symbol, interval="15m", period="3d", progress=False)
            df = df.dropna()

            close = df["Close"]
            low = df["Low"]
            high = df["High"]

            rsi15 = rsi_tv(close)
            df1h = df.resample("1h").last().dropna()
            rsi1h = rsi_tv(df1h["Close"])

            rsi_prev = rsi15.iloc[-3]
            rsi_now = rsi15.iloc[-2]
            rsi1h_now = rsi1h.iloc[-1]

            price = close.iloc[-2]

            if symbol in open_trades:
                continue

            # BUY
            if rsi1h_now > 60 and rsi_prev < 60 and rsi_now > 60:
                sl = low.iloc[-2]
                open_trades[symbol] = {
                    "type": "BUY",
                    "entry": price,
                    "sl": sl
                }
                send_telegram(f"BUY {symbol} @ {price} SL:{sl}")

            # SELL
            elif rsi1h_now < 60 and rsi_prev > 40 and rsi_now < 40:
                sl = high.iloc[-2]
                open_trades[symbol] = {
                    "type": "SELL",
                    "entry": price,
                    "sl": sl
                }
                send_telegram(f"SELL {symbol} @ {price} SL:{sl}")

        except Exception as e:
            print(symbol, e)

# ================= EXIT =================
def check_exit():
    for symbol in list(open_trades.keys()):
        try:
            df = yf.download(symbol, interval="15m", period="3d", progress=False)
            df = df.dropna()

            close = df["Close"]
            low = df["Low"]
            high = df["High"]
            rsi15 = rsi_tv(close)

            price = close.iloc[-2]
            rsi_now = rsi15.iloc[-2]

            trade = open_trades[symbol]
            entry = trade["entry"]
            sl = trade["sl"]

            # BUY
            if trade["type"] == "BUY":

                # STOPLOSS
                if low.iloc[-2] < sl:
                    pnl = price - entry
                    send_telegram(f"SL HIT BUY {symbol} @ {price}")
                    log_trade(symbol,"BUY",entry,price,pnl,"STOPLOSS")
                    del open_trades[symbol]
                    continue

                # TARGET 5%
                if price >= entry * 1.05:
                    pnl = price - entry
                    send_telegram(f"TARGET 5% BUY {symbol}")
                    log_trade(symbol,"BUY",entry,price,pnl,"TARGET_5%")
                    del open_trades[symbol]
                    continue

                # RSI EXIT
                if rsi_now < 60:
                    pnl = price - entry
                    send_telegram(f"RSI EXIT BUY {symbol}")
                    log_trade(symbol,"BUY",entry,price,pnl,"TARGET_RSI")
                    del open_trades[symbol]

            # SELL
            elif trade["type"] == "SELL":

                if high.iloc[-2] > sl:
                    pnl = entry - price
                    send_telegram(f"SL HIT SELL {symbol}")
                    log_trade(symbol,"SELL",entry,price,pnl,"STOPLOSS")
                    del open_trades[symbol]
                    continue

                if price <= entry * 0.95:
                    pnl = entry - price
                    send_telegram(f"TARGET 5% SELL {symbol}")
                    log_trade(symbol,"SELL",entry,price,pnl,"TARGET_5%")
                    del open_trades[symbol]
                    continue

                if rsi_now > 40:
                    pnl = entry - price
                    send_telegram(f"RSI EXIT SELL {symbol}")
                    log_trade(symbol,"SELL",entry,price,pnl,"TARGET_RSI")
                    del open_trades[symbol]

        except Exception as e:
            print("EXIT ERROR", symbol, e)

# ================= NEWS =================
news_sent = False
csv_sent = False

def send_news():
    send_telegram("📰 MARKET OPEN - BOT ACTIVE")

# ================= MAIN =================
print("🚀 BOT STARTED")

try:
    send_telegram("✅ BOT STARTED SUCCESSFULLY")
except Exception as e:
    print("Startup Telegram failed:", e)

last_run = None

while True:
    try:
    now = now_ist()

    # NEWS WINDOW FIX
    if now.hour == 8 and 30 <= now.minute <= 35 and not news_sent:
        send_news()
        news_sent = True

    # RESET DAILY
    if now.hour == 0:
        news_sent = False
        csv_sent = False

    # SEND CSV
    if now.hour == 15 and 35 <= now.minute <= 40 and not csv_sent:
        send_csv()
        csv_sent = True

    if is_market_open() and is_candle_close():

        if last_run != now.minute:
            run_bot()
            check_exit()
            last_run = now.minute

        time.sleep(5)
    else:
        time.sleep(20)
    except Exception as e:
        print("MAIN LOOP ERROR:", e)
        time.sleep(10)
