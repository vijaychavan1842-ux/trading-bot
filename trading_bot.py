import yfinance as yf
import pandas as pd
import requests
import time
import csv
from datetime import datetime

# ================= TELEGRAM =================
TOKEN = "8717830004:AAEKMFUHs9mV4c0mrYalmX6zmuJ3knKcnBo"
CHAT_ID = "538248415"

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg})
    except:
        print("Telegram Error")

# ================= SYMBOLS =================

# NIFTY 50
nifty50 = [
"RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS","SBIN.NS",
"ITC.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS","HCLTECH.NS","ASIANPAINT.NS",
"MARUTI.NS","SUNPHARMA.NS","TITAN.NS","ULTRACEMCO.NS","NESTLEIND.NS",
"BAJFINANCE.NS","BAJAJFINSV.NS","POWERGRID.NS","NTPC.NS","ONGC.NS",
"TATAMOTORS.NS","M&M.NS","WIPRO.NS","TECHM.NS","INDUSINDBK.NS",
"ADANIENT.NS","ADANIPORTS.NS","COALINDIA.NS","JSWSTEEL.NS","TATASTEEL.NS",
"HINDALCO.NS","GRASIM.NS","BRITANNIA.NS","EICHERMOT.NS","HEROMOTOCO.NS",
"CIPLA.NS","DRREDDY.NS","APOLLOHOSP.NS","DIVISLAB.NS","SBILIFE.NS",
"HDFCLIFE.NS","ICICIPRULI.NS","BAJAJ-AUTO.NS","SHREECEM.NS","UPL.NS",
"BPCL.NS","IOC.NS"
]

# BANKNIFTY
banknifty = [
"HDFCBANK.NS","ICICIBANK.NS","AXISBANK.NS","KOTAKBANK.NS",
"SBIN.NS","INDUSINDBK.NS","BANDHANBNK.NS","FEDERALBNK.NS",
"PNB.NS","IDFCFIRSTB.NS","AUBANK.NS","BANKBARODA.NS"
]

# INDEX
index_symbols = ["^NSEI", "^NSEBANK"]

# COMBINED
symbols = list(set(nifty50 + banknifty + index_symbols))

# ================= SAFE VALUE =================
def safe_value(x):
    try:
        if isinstance(x, pd.Series):
            return float(x.iloc[-1])
        return float(x)
    except:
        return 0

# ================= RSI =================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ================= VWAP =================
def calculate_vwap(df):
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    vp = tp * df["Volume"]
    return vp.cumsum() / df["Volume"].cumsum()

# ================= VOLUME =================
def get_volume_strength(df):
    if "Volume" not in df:
        return 0
    vol = df["Volume"]
    if isinstance(vol, pd.DataFrame):
        vol = vol.iloc[:, 0]

    current = safe_value(vol.iloc[-2])
    avg = vol.tail(20).mean()

    if avg == 0:
        return 0

    return round(current / avg, 2)

# ================= TRADE LOG =================
def log_trade(symbol, strategy, price):
    with open("trade_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now(), symbol, strategy, price])

# ================= MEMORY =================
last_signal = {}

# ================= MAIN BOT =================
def run_bot():
    global last_signal

    for symbol in symbols:
        try:
            print(f"Checking {symbol}...")

            df = yf.download(symbol, interval="15m", period="5d", progress=False)

            if df.empty:
                continue

            df = df.dropna()

            close = df["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]

            # ===== RSI =====
            rsi15 = calculate_rsi(close)

            df_1h = df.resample("1h").last().dropna()
            close_1h = df_1h["Close"]

            if isinstance(close_1h, pd.DataFrame):
                close_1h = close_1h.iloc[:, 0]

            rsi1h = calculate_rsi(close_1h)

            if len(rsi15) < 30 or len(rsi1h) < 20:
                continue

            # ===== CLOSED CANDLE VALUES =====
            rsi15_latest = safe_value(rsi15.iloc[-2])
            rsi15_prev = safe_value(rsi15.iloc[-3])
            rsi1h_latest = safe_value(rsi1h.iloc[-1])

            price = safe_value(close.iloc[-2])

            vwap_series = calculate_vwap(df)
            vwap = safe_value(vwap_series.iloc[-2])

            volume = get_volume_strength(df)

            strategy = None

            # ===== RSI 60 CONFIRMED =====
            if rsi1h_latest > 60 and rsi15_prev < 60 and rsi15_latest > 60:
                strategy = "BUY_RSI60_CONFIRMED"

            elif rsi1h_latest < 60 and rsi15_prev > 40 and rsi15_latest < 40:
                strategy = "SELL_RSI40_CONFIRMED"

            # ===== EXECUTION =====
            if strategy and last_signal.get(symbol) != strategy:

                if "BUY" in strategy:
                    sl = price * 0.98
                    target = price * 1.04
                else:
                    sl = price * 1.02
                    target = price * 0.96

                msg = (
                    f"🚨 {strategy}\n\n"
                    f"📊 {symbol}\n"
                    f"💰 Price: {round(price,2)}\n\n"
                    f"📉 RSI 1H: {round(rsi1h_latest,2)}\n"
                    f"📉 RSI 15m Prev: {round(rsi15_prev,2)}\n"
                    f"📉 RSI 15m Closed: {round(rsi15_latest,2)}\n\n"
                    f"📊 VWAP: {round(vwap,2)}\n"
                    f"📦 Volume: {volume}x\n\n"
                    f"🎯 SL: {round(sl,2)}\n"
                    f"🚀 Target: {round(target,2)}"
                )

                print(msg)
                send_telegram(msg)
                log_trade(symbol, strategy, price)

                last_signal[symbol] = strategy

        except Exception as e:
            print(f"Error {symbol}: {e}")

# ================= LOOP =================
print("🚀 FULL MARKET BOT STARTED")

try:
    while True:
        run_bot()
        print("⏳ Next scan in 60 sec...\n")
        time.sleep(60)

except KeyboardInterrupt:
    print("🛑 Bot stopped")