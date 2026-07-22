import yfinance as yf
import pandas as pd
import requests
import time
import csv
from datetime import datetime
import pytz
import os
import numpy as np

# ================= TELEGRAM =================
def send_telegram(msg):
    try:
        token = str(os.getenv("TOKEN")).strip()
        chat_id = str(os.getenv("CHAT_ID")).strip()

        if not token or token == "None" or not chat_id or chat_id == "None":
            print("Telegram not configured, message:", msg)
            return

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
    if now.weekday() >= 5:  # 0-4 = Mon-Fri
        return False
    start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    end   = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return start <= now <= end

# ================= SUPER TREND (FIXED) =================
def supertrend(df, period=7, multiplier=3):
    """
    Returns a pandas.Series with SuperTrend values (TradingView-style logic).
    """
    df = df.copy()

    if len(df) < period + 5:
        # not enough data to compute reliable ATR / ST
        return pd.Series(index=df.index, dtype=float)

    # True Range
    df['prev_close'] = df['Close'].shift(1)
    df['tr1'] = df['High'] - df['Low']
    df['tr2'] = (df['High'] - df['prev_close']).abs()
    df['tr3'] = (df['Low'] - df['prev_close']).abs()
    df['TR'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

    # ATR (simple moving average of TR)
    df['ATR'] = df['TR'].rolling(window=period).mean()

    # Basic bands
    hl2 = (df['High'] + df['Low']) / 2
    upperband = hl2 + multiplier * df['ATR']
    lowerband = hl2 - multiplier * df['ATR']

    final_upper = upperband.copy()
    final_lower = lowerband.copy()

    # Final upper/lower band logic
    for i in range(1, len(df)):
        if upperband.iloc[i] < final_upper.iloc[i-1] or df['Close'].iloc[i-1] > final_upper.iloc[i-1]:
            final_upper.iloc[i] = upperband.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i-1]

        if lowerband.iloc[i] > final_lower.iloc[i-1] or df['Close'].iloc[i-1] < final_lower.iloc[i-1]:
            final_lower.iloc[i] = lowerband.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i-1]

    st = pd.Series(index=df.index, dtype=float)

    # SuperTrend line selection
    for i in range(1, len(df)):
        if df['Close'].iloc[i] <= final_upper.iloc[i]:
            st.iloc[i] = final_upper.iloc[i]
        else:
            st.iloc[i] = final_lower.iloc[i]

    return st

# ================= SYMBOLS & STATE =================
symbols = {
    "^NSEI": 15,
    "^NSEBANK": 80,
    "RELIANCE.NS": 8,
    "TCS.NS": 8,
    "HDFCBANK.NS": 8,
    "GC=F": 600  # test
}

open_trades = {}  # {symbol: {"type": "BUY"/"SELL", "entry": float, "sl": float}}

# ================= CSV =================
def init_csv():
    if not os.path.exists("trade_log_day.csv"):
        with open("trade_log_day.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Time","Symbol","Type","Entry","SL","Exit","PnL","Reason"])

def log_trade(symbol, ttype, entry, sl, exit_price, pnl, reason):
    with open("trade_log_day.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([now_ist().strftime("%Y-%m-%d %H:%M:%S"), symbol, ttype, entry, sl, exit_price, pnl, reason])

# ================= ENTRY =================
def run_bot():
    for symbol, threshold in symbols.items():
        try:
            # More data than 2d to stabilize ATR/ST
            df = yf.download(symbol, interval="5m", period="5d", progress=False).dropna()
            if df.empty:
                continue

            close = df["Close"]
            st = supertrend(df)

            if len(st.dropna()) < 2:
                # Not enough valid ST values
                continue

            prev_st = st.dropna().iloc[-2]
            current_price = close.iloc[-1]

            if np.isnan(prev_st):
                continue

            diff = abs(current_price - prev_st)

            # skip if already in a trade for this symbol
            if symbol in open_trades:
                continue

            # ENTRY CONDITION: price within threshold of previous SuperTrend
            if diff <= threshold:
                # BUY
                if current_price > prev_st:
                    open_trades[symbol] = {
                        "type": "BUY",
                        "entry": current_price,
                        "sl": prev_st
                    }
                    send_telegram(f"🟢 BUY {symbol} @ {round(current_price,2)} | ST(prev)={round(prev_st,2)}")
                    print(f"BUY {symbol} @ {current_price} SL(ref ST)={prev_st}")

                # SELL
                else:
                    open_trades[symbol] = {
                        "type": "SELL",
                        "entry": current_price,
                        "sl": prev_st
                    }
                    send_telegram(f"🔴 SELL {symbol} @ {round(current_price,2)} | ST(prev)={round(prev_st,2)}")
                    print(f"SELL {symbol} @ {current_price} SL(ref ST)={prev_st}")

        except Exception as e:
            print("ENTRY ERROR:", symbol, e)

# ================= EXIT =================
def check_exit():
    for symbol in list(open_trades.keys()):
        try:
            df = yf.download(symbol, interval="5m", period="5d", progress=False).dropna()
            if df.empty:
                continue

            close = df["Close"]
            st = supertrend(df)

            if len(st.dropna()) == 0:
                continue

            last_close = close.iloc[-1]
            last_st = st.dropna().iloc[-1]
            current_price = last_close  # same

            trade = open_trades[symbol]
            entry = trade["entry"]

            # STOPLOSS: candle close vs current ST
            if trade["type"] == "BUY" and last_close < last_st:
                pnl = current_price - entry
                send_telegram(f"❌ SL BUY {symbol} Exit:{round(current_price,2)} PnL:{round(pnl,2)}")
                log_trade(symbol, "BUY", entry, last_st, current_price, pnl, "SL")
                print(f"SL BUY {symbol} entry={entry}, exit={current_price}, pnl={pnl}")
                del open_trades[symbol]

            elif trade["type"] == "SELL" and last_close > last_st:
                pnl = entry - current_price
                send_telegram(f"❌ SL SELL {symbol} Exit:{round(current_price,2)} PnL:{round(pnl,2)}")
                log_trade(symbol, "SELL", entry, last_st, current_price, pnl, "SL")
                print(f"SL SELL {symbol} entry={entry}, exit={current_price}, pnl={pnl}")
                del open_trades[symbol]

            # TARGET: fixed 10% from entry
            elif trade["type"] == "BUY" and current_price >= entry * 1.10:
                pnl = current_price - entry
                send_telegram(f"🎯 TARGET BUY {symbol} Exit:{round(current_price,2)} PnL:{round(pnl,2)}")
                log_trade(symbol, "BUY", entry, last_st, current_price, pnl, "TARGET")
                print(f"TARGET BUY {symbol} entry={entry}, exit={current_price}, pnl={pnl}")
                del open_trades[symbol]

            elif trade["type"] == "SELL" and current_price <= entry * 0.90:
                pnl = entry - current_price
                send_telegram(f"🎯 TARGET SELL {symbol} Exit:{round(current_price,2)} PnL:{round(pnl,2)}")
                log_trade(symbol, "SELL", entry, last_st, current_price, pnl, "TARGET")
                print(f"TARGET SELL {symbol} entry={entry}, exit={current_price}, pnl={pnl}")
                del open_trades[symbol]

        except Exception as e:
            print("EXIT ERROR:", symbol, e)

# ================= CSV EXPORT =================
def export_csv():
    now = now_ist()
    if os.path.exists("trade_log_day.csv"):
        # e.g., end-of-day export/rename
        if now.hour == 15 and now.minute == 35:
            new_name = f"trade_log_335_{now.date()}.csv"
            if not os.path.exists(new_name):
                os.rename("trade_log_day.csv", new_name)
        if now.hour == 23 and now.minute == 5:
            new_name = f"trade_log_1105_{now.date()}.csv"
            if not os.path.exists(new_name):
                os.rename("trade_log_day.csv", new_name)

# ================= MAIN =================
if __name__ == "__main__":
    print("🚀 BOT STARTED")
    send_telegram("✅ BOT LIVE")
    init_csv()

    while True:
        try:
            if is_market_open():
                run_bot()
                check_exit()
                export_csv()
                time.sleep(5)   # 5-second cycle during market hours
            else:
                time.sleep(20)  # slower loop outside market hours
        except Exception as e:
            print("MAIN ERROR:", e)
            time.sleep(10)
