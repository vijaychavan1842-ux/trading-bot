import yfinance as yf
import pandas as pd
import requests
import time
import csv
from datetime import datetime
import pytz
import os

# ================= TELEGRAM =================
TOKEN = os.getenv("8717830004:AAEKMFUHs9mV4c0mrYalmX6zmuJ3knKcnBo")
CHAT_ID = os.getenv("538248415")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg})
    except:
        print("Telegram Error")

# ================= TIME =================
india = pytz.timezone('Asia/Kolkata')

def now_ist():
    return datetime.now(india)

# ================= MARKET TIME =================
def is_market_open():
    now = now_ist()
    if now.weekday() >= 5:
        return False

    start = now.replace(hour=9, minute=30)
    end = now.replace(hour=15, minute=30)

    return start <= now <= end

# ================= 15 MIN CLOSE =================
def is_candle_close():
    now = now_ist()
    return now.minute % 15 == 0 and now.second < 5

# ================= RSI (TradingView Style) =================
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
"LT.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS",
"TITAN.NS","ULTRACEMCO.NS","NESTLEIND.NS","WIPRO.NS","TECHM.NS",
"POWERGRID.NS","NTPC.NS","BAJFINANCE.NS","BAJAJFINSV.NS","HCLTECH.NS",
"ONGC.NS","JSWSTEEL.NS","TATASTEEL.NS","INDUSINDBK.NS","ADANIENT.NS",
"ADANIPORTS.NS","COALINDIA.NS","BRITANNIA.NS","EICHERMOT.NS","HEROMOTOCO.NS",
"DIVISLAB.NS","DRREDDY.NS","CIPLA.NS","GRASIM.NS","APOLLOHOSP.NS",
"BAJAJ-AUTO.NS","BPCL.NS","HDFCLIFE.NS","SBILIFE.NS","ICICIPRULI.NS",
"TATACONSUM.NS","UPL.NS","SHREECEM.NS","M&M.NS","LTIM.NS",

# BANKNIFTY
"HDFCBANK.NS","ICICIBANK.NS","AXISBANK.NS","KOTAKBANK.NS",
"SBIN.NS","INDUSINDBK.NS","BANDHANBNK.NS","FEDERALBNK.NS",
"PNB.NS","IDFCFIRSTB.NS","AUBANK.NS","BANKBARODA.NS",

# INDEX
"^NSEI","^NSEBANK"
]

# ================= STORAGE =================
open_trades = {}
last_signal = {}

# ================= TRADE LOG =================
def log_trade(symbol, trade_type, entry, exit_price, pnl, result):
    file = "trade_log.csv"

    file_exists = False
    try:
        with open(file, "r"):
            file_exists = True
    except:
        pass

    with open(file, "a", newline="") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(["Time","Symbol","Type","Entry","Exit","PnL","Result"])

        writer.writerow([
            datetime.now(),
            symbol,
            trade_type,
            round(entry,2),
            round(exit_price,2),
            round(pnl,2),
            result
        ])

# ================= ENTRY =================
def run_bot():
    global open_trades

    for symbol in symbols:
        try:
            df = yf.download(symbol, interval="15m", period="3d", progress=False, threads=False)
            df = df.dropna()

            close = df["Close"]
            rsi15 = rsi_tv(close)

            df1h = df.resample("1h").last().dropna()
            rsi1h = rsi_tv(df1h["Close"])

            rsi15_latest = float(rsi15.iloc[-2])
            rsi15_prev = float(rsi15.iloc[-3])
            rsi1h_latest = float(rsi1h.iloc[-1])
            price = float(close.iloc[-2])

            signal = None

            # ===== YOUR STRATEGY =====
            if rsi1h_latest > 60 and rsi15_prev < 60 and rsi15_latest > 60:
                signal = "BUY"

            elif rsi1h_latest < 60 and rsi15_prev > 40 and rsi15_latest < 40:
                signal = "SELL"

            if signal and symbol not in open_trades and last_signal.get(symbol) != signal:

                open_trades[symbol] = {
                    "type": signal,
                    "entry": price
                }

                msg = f"🚨 {signal} {symbol}\nPrice: {price}\nRSI Prev: {round(rsi15_prev,2)}\nRSI Close: {round(rsi15_latest,2)}"
                send_telegram(msg)

                last_signal[symbol] = signal

        except Exception as e:
            print(symbol, e)

# ================= EXIT =================
def check_exit():
    global open_trades

    for symbol in list(open_trades.keys()):
        try:
            df = yf.download(symbol, interval="15m", period="3d", progress=False, threads=False)
            df = df.dropna()

            close = df["Close"]
            rsi15 = rsi_tv(close)

            rsi_closed = float(rsi15.iloc[-2])
            price = float(close.iloc[-2])

            trade = open_trades[symbol]

            if trade["type"] == "BUY" and rsi_closed < 60:
                pnl = price - trade["entry"]
                result = "WIN" if pnl > 0 else "LOSS"

                send_telegram(f"❌ EXIT BUY {symbol} @ {price} | P&L: {round(pnl,2)}")
                log_trade(symbol, "BUY", trade["entry"], price, pnl, result)
                del open_trades[symbol]

            elif trade["type"] == "SELL" and rsi_closed > 40:
                pnl = trade["entry"] - price
                result = "WIN" if pnl > 0 else "LOSS"

                send_telegram(f"❌ EXIT SELL {symbol} @ {price} | P&L: {round(pnl,2)}")
                log_trade(symbol, "SELL", trade["entry"], price, pnl, result)
                del open_trades[symbol]

        except Exception as e:
            print("Exit error:", symbol, e)

# ================= MORNING NEWS =================
news_sent = False

def send_morning_news():
    try:
        msg = "📰 MARKET OPEN UPDATE\nTrade Safe Today"
        send_telegram(msg)
    except:
        pass

# ================= MAIN =================
print("🚀 FINAL BOT STARTED")

last_run = None

while True:
    now = now_ist()

    if now.hour == 8 and now.minute == 30 and not news_sent:
        send_morning_news()
        news_sent = True

    if now.hour == 0:
        news_sent = False

    if is_market_open() and is_candle_close():

        if last_run != now.minute:
            run_bot()
            check_exit()
            last_run = now.minute

        time.sleep(5)

    else:
        time.sleep(30)
