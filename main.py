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

def analyze(df, name, market_type):
    try:
        if df is None or len(df) < 35: return
        c = df['Close']
        prev_close = c.iloc[-2] 
        curr_price = c.iloc[-1]
        
        # RSI 14
        diff = c.diff()
        up = diff.where(diff > 0, 0).rolling(14).mean()
        down = (-diff.where(diff < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (up / (down + 1e-10))))
        curr_rsi = rsi.iloc[-1]

        # 지표 계산
        ma5 = c.rolling(5).mean()
        ma20 = c.rolling(20).mean()
        std20 = c.rolling(20).std()
        bbu, bbl = ma20 + (std20 * 2), ma20 - (std20 * 2)
        ema12, ema26 = c.ewm(span=12).mean(), c.ewm(span=26).mean()
        macd = ema12 - ema26
        pmacd = macd.iloc[-2]

        market_tag = f"[{market_type}]"
        
        # [매수 판정]
        if curr_rsi <= 40 and (market_type == "코인" or curr_price < prev_close):
            cond = []
            if (curr_price >= ma5.iloc[-1] * 0.98): cond.append("1")
            if (curr_price <= bbl.iloc[-1] * 1.03): cond.append("2")
            if (macd.iloc[-1] > pmacd): cond.append("3")
            
            if len(cond) >= 2: # 3개 중 2개 이상 만족 시
                send_alert(f"🟢{market_tag} {name} {curr_rsi:.0f} ({','.join(cond)})")

        # [매도 판정]
        elif curr_rsi >= 60 and (market_type == "코인" or curr_price > prev_close):
            m_cond = []
            if (curr_price <= ma5.iloc[-1] * 1.02): m_cond.append("1")
            if (curr_price >= bbu.iloc[-1] * 0.97): m_cond.append("2")
            if (macd.iloc[-1] < pmacd): m_cond.append("3")
            
            if len(m_cond) >= 2: # 3개 중 2개 이상 만족 시
                send_alert(f"🔴{market_tag} {name} {curr_rsi:.0f} ({','.join(m_cond)})")
    except: pass

# ... (이하 run_loop 함수 및 시장 시간 로직은 이전과 동일) ...
