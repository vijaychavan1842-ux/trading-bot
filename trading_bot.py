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
    return now.minute % 15 == 0 and now.second < 8

# ================= RSI =================
def rsi_tv(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ================= GLOBAL NEWS =================
def get_global_data():
    try:
        symbols = {
            "DOW": "^DJI",
            "S&P500": "^GSPC",
            "NASDAQ": "^IXIC",
            "GIFT NIFTY": "^NSEI"
        }

        msg = "🌍 GLOBAL MARKET UPDATE\n\n"

        for name, sym in symbols.items():
            df = yf.download(sym, period="2d", interval="1d", progress=False)
            change = df["Close"].iloc[-1] - df["Close"].iloc[-2]
            msg += f"{name}: {round(change,2)} pts\n"

        # crude
        oil = yf.download("CL=F", period="2d", interval="1d", progress=False)
        oil_change = oil["Close"].iloc[-1] - oil["Close"].iloc[-2]

        msg += f"Crude Oil: {round(oil_change,2)} pts\n"

        return msg

    except:
        return "Global data not available"

# ================= NEWS MESSAGE =================
def send_morning_news():
    global_data = get_global_data()

    msg = f"""
📊 MARKET MORNING UPDATE

{global_data}

🟢 POSITIVE FACTORS
• Global market positive → bullish sentiment
• Crude stable → inflation under control
• Strong closing in US → gap up chances

🔴 NEGATIVE FACTORS
• Weak global cues → selling pressure
• High crude → cost pressure
• Profit booking expected

🎯 PROBABLE IMPACT
• Gap Up → look for BUY above resistance
• Gap Down → look for SELL below support
• Sideways → avoid overtrading

🚀 BOT ACTIVE
"""

    send_telegram(msg)

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
# BANK
"HDFCBANK.NS","ICICIBANK.NS","AXISBANK.NS","KOTAKBANK.NS",
"SBIN.NS","INDUSINDBK.NS","BANKBARODA.NS","PNB.NS",
# INDEX
"^NSEI","^NSEBANK"
]

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

            if rsi1h_now > 60 and rsi_prev < 60 and rsi_now > 60:
                sl = low.iloc[-2]
                open_trades[symbol] = {"type":"BUY","entry":price,"sl":sl}
                send_telegram(f"BUY {symbol}\nEntry:{price}\nSL:{sl}")

            elif rsi1h_now < 60 and rsi_prev > 40 and rsi_now < 40:
                sl = high.iloc[-2]
                open_trades[symbol] = {"type":"SELL","entry":price,"sl":sl}
                send_telegram(f"SELL {symbol}\nEntry:{price}\nSL:{sl}")

        except Exception as e:
            print("ENTRY ERROR:", e)

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

            if trade["type"] == "BUY":

                if low.iloc[-2] < sl:
                    pnl = price-entry
                    send_telegram(f"SL BUY {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"BUY",entry,price,pnl,"SL")
                    del open_trades[symbol]

                elif price >= entry*1.05:
                    pnl = price-entry
                    send_telegram(f"TARGET BUY {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"BUY",entry,price,pnl,"TGT")
                    del open_trades[symbol]

                elif rsi_now < 60:
                    pnl = price-entry
                    send_telegram(f"RSI EXIT BUY {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"BUY",entry,price,pnl,"RSI")
                    del open_trades[symbol]

            else:

                if high.iloc[-2] > sl:
                    pnl = entry-price
                    send_telegram(f"SL SELL {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"SELL",entry,price,pnl,"SL")
                    del open_trades[symbol]

                elif price <= entry*0.95:
                    pnl = entry-price
                    send_telegram(f"TARGET SELL {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"SELL",entry,price,pnl,"TGT")
                    del open_trades[symbol]

                elif rsi_now > 40:
                    pnl = entry-price
                    send_telegram(f"RSI EXIT SELL {symbol} PnL:{round(pnl,2)}")
                    log_trade(symbol,"SELL",entry,price,pnl,"RSI")
                    del open_trades[symbol]

        except Exception as e:
            print("EXIT ERROR:", e)

# ================= MAIN =================
print("🚀 BOT STARTED")
send_telegram("✅ BOT LIVE")

news_sent = False
last_run = None

while True:
    try:
        now = now_ist()

        # MORNING NEWS
        if now.hour == 8 and 30 <= now.minute <= 35 and not news_sent:
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
            time.sleep(20)

    except Exception as e:
        print("MAIN ERROR:", e)
        time.sleep(10)
