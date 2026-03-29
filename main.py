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
        
        diff = c.diff()
        up = diff.where(diff > 0, 0).rolling(14).mean()
        down = (-diff.where(diff < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (up / (down + 1e-10))))
        curr_rsi = rsi.iloc[-1]

        ma5 = c.rolling(5).mean()
        ma20 = c.rolling(20).mean()
        std20 = c.rolling(20).std()
        bbu, bbl = ma20 + (std20 * 2), ma20 - (std20 * 2)
        ema12, ema26 = c.ewm(span=12).mean(), c.ewm(span=26).mean()
        macd = ema12 - ema26
        pmacd = macd.iloc[-2]

        if curr_rsi <= 40 and (market_type == "코인" or curr_price < prev_close):
            cond = []
            if (curr_price >= ma5.iloc[-1] * 0.98): cond.append("1")
            if (curr_price <= bbl.iloc[-1] * 1.03): cond.append("2")
            if (macd.iloc[-1] > pmacd): cond.append("3")
            if cond: send_alert(f"🟢[{market_type}] {name} {curr_rsi:.0f} ({','.join(cond)})")

        elif curr_rsi >= 60 and (market_type == "코인" or curr_price > prev_close):
            m_cond = []
            if (curr_price <= ma5.iloc[-1] * 1.02): m_cond.append("1")
            if (curr_price >= bbu.iloc[-1] * 0.97): m_cond.append("2")
            if (macd.iloc[-1] < pmacd): m_cond.append("3")
            if m_cond: send_alert(f"🔴[{market_type}] {name} {curr_rsi:.0f} ({','.join(m_cond)})")
    except: pass

def run_loop():
    send_alert("🚀 [전략 가동] 시장별 개장 시간 집중 감시 모드 시작")
    start_time = time.time()
    
    while True:
        # GitHub Actions 6시간 제한 대비 (약 5시간 30분 후 자동 재시작 유도)
        if time.time() - start_time > 20000: 
            break

        now = datetime.now(pytz.timezone('Asia/Seoul'))
        curr_time = now.hour * 100 + now.minute
        is_weekday = now.weekday() < 5

        # 1. 코인 (상위 10개, 24시간 무한 스캔)
        try:
            for t in pyupbit.get_tickers(fiat="KRW")[:10]:
                analyze(pyupbit.get_ohlcv(t, interval="minute1", count=50), t.split("-")[1], "코인")
                time.sleep(0.05)
        except: pass

        # 2. 한국 주식 (09:00 ~ 15:30 집중 스캔)
        if is_weekday and 900 <= curr_time <= 1530:
            try:
                krx = fdr.StockListing('KRX').sort_values('Marcap', ascending=False).head(100)
                for _, r in krx.iterrows():
                    analyze(fdr.DataReader(r['Code']).tail(50), r['Name'], "국장")
                    time.sleep(0.05)
            except: pass
        elif is_weekday and curr_time == 1531: # 종료 직후 1회 알림
            send_alert("🏁 [국장] 장 마감 - 스캔 종료")
            time.sleep(60)

        # 3. 미국 주식 (22:30 ~ 익일 05:00 집중 스캔)
        # 서머타임 미적용 기준 23:30~06:00이나, 넉넉하게 설정
        if is_weekday and (curr_time >= 2230 or curr_time <= 500):
            try:
                us = fdr.StockListing('S&P500').head(100)
                for _, r in us.iterrows():
                    analyze(fdr.DataReader(r['Symbol']).tail(50), r['Symbol'], "미장")
                    time.sleep(0.05)
            except: pass
        elif is_weekday and curr_time == 501: # 종료 직후 1회 알림
            send_alert("🏁 [미장] 장 마감 - 스캔 종료")
            time.sleep(60)

        # 스캔 후 1분 휴식 (API 과부하 방지 및 무한 반복)
        time.sleep(60)

if __name__ == "__main__":
    run_loop()
