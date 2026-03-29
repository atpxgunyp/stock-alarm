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
    try:
        if df is None or len(df) < 35: return None
        d = df[['Close']].copy()
        close = d['Close']
        
        # RSI (0 나누기 방지)
        diff = close.diff()
        up = diff.where(diff > 0, 0).rolling(window=14).mean()
        down = (-diff.where(diff < 0, 0)).rolling(window=14).mean()
        d['RSI'] = 100 - (100 / (1 + (up / (down + 1e-10))))
        
        # 지표 계산
        d['MA20'] = close.rolling(window=20).mean()
        d['STD20'] = close.rolling(window=20).std()
        d['BBU'] = d['MA20'] + (d['STD20'] * 2)
        d['BBL'] = d['MA20'] - (d['STD20'] * 2)
        d['MA5'] = close.rolling(window=5).mean()
        
        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        d['MACD'] = ema12 - ema26
        d['SIGNAL'] = d['MACD'].ewm(span=9, adjust=False).mean()
        
        return d
    except: return None

def analyze(df, name, is_coin=False):
    try:
        data = get_indicators(df)
        if data is None: return
        
        c, p = data.iloc[-1], data.iloc[-2]
        if pd.isna(c['RSI']): return

        msg = []
        # 매수/매도 로직
        if c['RSI'] < 45 and c['Close'] < p['Close']:
            if c['Close'] > c['MA5'] * 0.97: msg.append("✅ 5일선 지지")
            if c['Close'] < c['BBL'] * 1.05: msg.append("✅ 하단 밴드 영역")
            if c['MACD'] > c['SIGNAL']: msg.append("✅ MACD 우상향")
            if msg:
                tag = "🪙 [코인매수]" if is_coin else "🟢 [주식매수]"
                send_alert(f"{tag} {name}\n가: {c['Close']:,.0f}\nRSI: {c['RSI']:.1f}\n" + "\n".join(msg))
        elif c['RSI'] > 55 and c['Close'] > p['Close']:
            if c['Close'] < c['MA5'] * 1.03: msg.append("❌ 5일선 이탈")
            if c['Close'] > c['BBU'] * 0.95: msg.append("❌ 상단 밴드 영역")
            if c['MACD'] < c['SIGNAL']: msg.append("❌ MACD 우하향")
            if msg:
                tag = "🪙 [코인매도]" if is_coin else "🔴 [주식매도]"
                send_alert(f"{tag} {name}\n가: {c['Close']:,.0f}\nRSI: {c['RSI']:.1f}\n" + "\n".join(msg))
    except: pass

def scan_market():
    # 1. 코인 스캔 (언제나 실행)
    for t in ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE"]:
        try:
            df = pyupbit.get_ohlcv(t, interval="day", count=60)
            if df is not None: analyze(df, t.replace("KRW-",""), True)
            time.sleep(0.2)
        except: continue

    # 2. 주식 시간대 체크 (한국 시간 기준)
    tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(tz)
    curr = now.hour * 100 + now.minute
    
    # 평일 주식 스캔 (주말엔 코인만 하고 종료)
    if now.weekday() < 5:
        # 한국 장 시간 (09:00 ~ 15:40)
        if 900 <= curr <= 1540:
            try:
                krx = fdr.StockListing('KRX').head(50) # 시총 상위 50개
                for _, row in krx.iterrows():
                    try:
                        df = fdr.DataReader(row['Code']).tail(60)
                        analyze(df, row['Name'])
                        time.sleep(0.2)
                    except: continue
            except: pass
            
        # 미국 장 시간 (22:30 ~ 05:00)
        elif curr >= 2230 or curr <= 500:
            try:
                sp500 = fdr.StockListing('S&P500').head(50) # 상위 50개
                for _, row in sp500.iterrows():
                    try:
                        df = fdr.DataReader(row['Symbol']).tail(60)
                        analyze(df, row['Symbol'])
                        time.sleep(0.2)
                    except: continue
            except: pass

if __name__ == "__main__":
    scan_market()
