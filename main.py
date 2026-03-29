import FinanceDataReader as fdr
import pyupbit
import os, requests, pytz, time
from datetime import datetime

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def send_alert(msg):
    if not (TOKEN and CHAT_ID): return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except: pass

def analyze(df, name, is_coin=False):
    try:
        if df is None or len(df) < 35: return
        c = df['Close']
        prev_close = c.iloc[-2] 
        curr_price = c.iloc[-1]
        
        # RSI 14 (문턱 40/60)
        diff = c.diff()
        up = diff.where(diff > 0, 0).rolling(14).mean()
        down = (-diff.where(diff < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (up / (down + 1e-10))))
        curr_rsi = rsi.iloc[-1]

        # 지표 계산 (초민감형)
        ma5 = c.rolling(5).mean()
        ma20 = c.rolling(20).mean()
        std20 = c.rolling(20).std()
        bbu, bbl = ma20 + (std20 * 2), ma20 - (std20 * 2)
        ema12, ema26 = c.ewm(span=12).mean(), c.ewm(span=26).mean()
        macd = ema12 - ema26
        pmacd = macd.iloc[-2]

        # [매수] RSI 40 이하 + (주식은 전일종가 미만 필수)
        if curr_rsi <= 40 and (is_coin or curr_price < prev_close):
            cond = []
            if (curr_price >= ma5.iloc[-1] * 0.98): cond.append("1")
            if (curr_price <= bbl.iloc[-1] * 1.03): cond.append("2")
            if (macd.iloc[-1] > pmacd): cond.append("3")
            if cond:
                send_alert(f"{"🪙" if is_coin else "🟢"} {name} {curr_rsi:.0f} ({','.join(cond)})")

        # [매도] RSI 60 이상 + (주식은 전일종가 초과 필수)
        elif curr_rsi >= 60 and (is_coin or curr_price > prev_close):
            m_cond = []
            if (curr_price <= ma5.iloc[-1] * 1.02): m_cond.append("1")
            if (curr_price >= bbu.iloc[-1] * 0.97): m_cond.append("2")
            if (macd.iloc[-1] < pmacd): m_cond.append("3")
            if m_cond:
                send_alert(f"{"🪙" if is_coin else "🔴"} {name} {curr_rsi:.0f} ({','.join(m_cond)})")
    except: pass

def run():
    now = datetime.now(pytz.timezone('Asia/Seoul'))
    curr_time = now.hour * 100 + now.minute

    # 장 종료 알림
    if 1540 <= curr_time <= 1600 and now.weekday() < 5:
        send_alert("🇰🇷 한국 시장 종료")
        return 
    if 500 <= curr_time <= 530 and now.weekday() < 5:
        send_alert("🇺🇸 미국 시장 종료")
        return

    # 1. 코인 상위 10개 (24시간)
    try:
        coins = pyupbit.get_tickers(fiat="KRW")[:10]
        for t in coins:
            analyze(pyupbit.get_ohlcv(t, count=50), t.split("-")[1], True)
            time.sleep(0.05)
    except: pass

    # 2. 한국 주식 상위 100개
    if now.weekday() < 5 and 900 <= curr_time < 1540:
        try:
            krx = fdr.StockListing('KRX').sort_values('Marcap', ascending=False).head(100)
            for _, r in krx.iterrows():
                analyze(fdr.DataReader(r['Code']).tail(50), r['Name'])
                time.sleep(0.05)
        except: pass

    # 3. 미국 주식 상위 100개
    if curr_time >= 2230 or curr_time < 500:
        try:
            us = fdr.StockListing('S&P500').head(100)
            for _, r in us.iterrows():
                analyze(fdr.DataReader(r['Symbol']).tail(50), r['Symbol'])
                time.sleep(0.05)
        except: pass

if __name__ == "__main__":
    run()
