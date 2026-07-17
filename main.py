import threading
import os

def run_rsi():
    os.system("python trading_bot.py")

def run_st():
    os.system("python supertrend_bot.py")

t1 = threading.Thread(target=run_rsi)
t2 = threading.Thread(target=run_st)

t1.start()
t2.start()

t1.join()
t2.join()
