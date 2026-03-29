import FinanceDataReader as fdr
import pyupbit
import os, requests, pytz, time
import pandas as pd
from datetime import datetime

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def send_alert(message):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except: pass

def get_indicators(df):
    """라이브러리 없이 지표 직접 계산 (오류 방지)"""
    try:
        close = df['Close']
        # 1. RSI 계산
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 2. 볼린저 밴드
        df['MA20'] = close.rolling(window=20).mean()
        df['STD20'] = close.rolling(window=20).std()
        df['BBU'] = df['MA20'] + (df['STD20'] * 2)
        df['BBL'] = df['MA20'] - (df['STD20'] * 2)
        
        # 3. MACD
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['SIGNAL'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # 4. 5일 이동평균
        df['MA5'] = close.rolling(window=5).mean()
        return df
    except: return None

def analyze_logic(df, name, is_coin=False):
    try:
        df = get_indicators(df)
        if df is None or len(df) < 30: return
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        curr_p, prev_p = curr['Close'], prev['Close']
        
        conds = []
        # 매수 조건 (RSI 45 미만 + 하락 중)
        if curr['RSI'] < 45 and curr_p < prev_p:
            if curr_p > curr['MA5'] * 0.97: conds.append("✅ 5일선 근접/돌파")
            if curr_p < curr['BBL'] * 1.07: conds.append("✅ 볼린저 하단영역")
            if curr['MACD'] > curr['SIGNAL']: conds.append("✅ MACD 우상향")
            if conds:
                tag = "🪙 [코인매수]" if is_coin else "🟢 [주식매수]"
                send_alert(f"{tag} {name}\n가: {curr_p:,.0f}\nRSI: {curr['RSI']:.1f}\n" + "\n".join(conds))

        # 매도 조건 (RSI 55 초과 + 상승 중)
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
            for _, row in stocks.iterrows():
                try:
                    df = fdr.DataReader(row['Code']).tail(100)
                    analyze_logic(df, row['Name'])
                    time.sleep(0.05)
                except: continue
        else:
            stocks = fdr.StockListing('S&P500').head(100)
            for _, row in stocks.iterrows():
                try:
                    df = fdr.DataReader(row['Symbol']).tail(100)
                    analyze_logic(df, row['Symbol'])
                    time.sleep(0.05)
                except: continue
    except: pass

def scan_coins():
    tickers = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-ADA", "KRW-DOGE", "KRW-DOT", "KRW-TRX", "KRW-AVAX", "KRW-LINK"]
    for t in tickers:
        try:
            df = pyupbit.get_ohlcv(t, interval="day", count=100)
            if df is not None: analyze_logic(df, t.replace("KRW-",""), is_coin=True)
            time.sleep(0.05)
        except: continue

if __name__ == "__main__":
    scan_coins()
    # 장 상태 확인 (주말엔 OFF)
    seoul_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_tz)
    curr_time = now.hour * 100 + now.minute
    
    if now.weekday() < 5: # 평일일 때만 주식 스캔
        if 900 <= curr_time <= 1540: scan_stocks("KOREA")
        elif curr_time >= 2230 or curr_time <= 500: scan_stocks("USA")
