import FinanceDataReader as fdr
import pyupbit
import os, requests, pytz, time
import pandas as pd
from datetime import datetime

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def send_alert(message):
    if not TOKEN or not CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except: pass

def get_indicators(df):
    """라이브러리 없이 직접 계산 (에러 발생 시 None 반환)"""
    try:
        if df is None or len(df) < 30: return None
        df = df.copy()
        close = df['Close']
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))
        
        # BB / MA
        df['MA20'] = close.rolling(window=20).mean()
        df['STD20'] = close.rolling(window=20).std()
        df['BBU'] = df['MA20'] + (df['STD20'] * 2)
        df['BBL'] = df['MA20'] - (df['STD20'] * 2)
        df['MA5'] = close.rolling(window=5).mean()
        
        # MACD
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['SIGNAL'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        return df
    except: return None

def analyze_logic(df, name, is_coin=False):
    try:
        df = get_indicators(df)
        if df is None: return
        
        curr, prev = df.iloc[-1], df.iloc[-2]
        curr_p, prev_p = curr['Close'], prev['Close']
        
        conds = []
        if curr['RSI'] < 45 and curr_p < prev_p:
            if curr_p > curr['MA5'] * 0.97: conds.append("✅ 5일선 근접/돌파")
            if curr_p < curr['BBL'] * 1.07: conds.append("✅ 볼린저 하단영역")
            if curr['MACD'] > curr['SIGNAL']: conds.append("✅ MACD 우상향")
            if conds:
                tag = "🪙 [코인매수]" if is_coin else "🟢 [주식매수]"
                send_alert(f"{tag} {name}\n가: {curr_p:,.0f}\nRSI: {curr['RSI']:.1f}\n" + "\n".join(conds))
        elif curr['RSI'] > 55 and curr_p > prev_p:
            if curr_p < curr['MA5'] * 1.03: conds.append("❌ 5일선 이탈징후")
            if curr_p > curr['BBU'] * 0.93: conds.append("❌ 볼린저 상단영역")
            if curr['MACD'] < curr['SIGNAL']: conds.append("❌ MACD 우하향")
            if conds:
                tag = "🪙 [코인매도]" if is_coin else "🔴 [주식매도]"
                send_alert(f"{tag} {name}\n가: {curr_p:,.0f}\nRSI: {curr['RSI']:.1f}\n" + "\n".join(conds))
    except: pass

def scan_stocks(m_type):
    try:
        if m_type == "KOREA":
            stocks = fdr.StockListing('KRX').sort_values('Marcap', ascending=False).head(100)
            target_col, name_col = 'Code', 'Name'
        else:
            stocks = fdr.StockListing('S&P500').head(100)
            target_col, name_col = 'Symbol', 'Symbol'

        for _, row in stocks.iterrows():
            try:
                df = fdr.DataReader(row[target_col]).tail(100)
                if not df.empty: analyze_logic(df, row[name_col])
                time.sleep(0.1)
            except: continue # 에러 나면 그냥 다음 종목으로!
    except: pass

def scan_coins():
    tickers = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-ADA", "KRW-DOGE", "KRW-DOT", "KRW-TRX", "KRW-AVAX", "KRW-LINK"]
    for t in tickers:
        try:
            df = pyupbit.get_ohlcv(t, interval="day", count=100)
            if df is not None: analyze_logic(df, t.replace("KRW-",""), is_coin=True)
            time.sleep(0.1)
        except: continue

if __name__ == "__main__":
    # 1. 코인 스캔 (에러 방지를 위해 독립 실행)
    try: scan_coins()
    except: pass

    # 2. 주식 스캔 (시간대 확인)
    try:
        seoul_tz = pytz.timezone('Asia/Seoul')
        now = datetime.now(seoul_tz)
        curr = now.hour * 100 + now.minute
        if now.weekday() < 5:
            if 900 <= curr <= 1540: scan_stocks("KOREA")
            elif curr >= 2230 or curr <= 500: scan_stocks("USA")
    except: pass
