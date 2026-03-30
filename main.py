import FinanceDataReader as fdr
import pyupbit
import os, requests, pytz, time
from datetime import datetime

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
last_msg_id = 0 # 중복 응답 방지용

def send_alert(msg):
    if not (TOKEN and CHAT_ID): return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except: pass

def check_status_request():
    """텔레그램 메시지 확인: '작동?' 질문에 응답"""
    global last_msg_id
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        response = requests.get(url, params={"offset": -1, "timeout": 5}).json()
        if response.get("ok") and response.get("result"):
            last_update = response["result"][-1]
            msg_text = last_update.get("message", {}).get("text", "")
            msg_id = last_update.get("update_id")
            if ("작동?" in msg_text or "상태?" in msg_text) and msg_id != last_msg_id:
                now = datetime.now(pytz.timezone('Asia/Seoul'))
                send_alert(f"✅ 정상 가동 중입니다!\n🕒 확인 시각: {now.strftime('%H:%M:%S')}\n📊 코스피50/미장/코인 스캔 중")
                last_msg_id = msg_id
    except: pass

def analyze(df, name, market_type):
    try:
        if df is None or len(df) < 35: return
        c = df['Close']
        prev_close, curr_price = c.iloc[-2], c.iloc[-1]
        
        # RSI 14 (문턱 낮춤: 45/55)
        diff = c.diff()
        up = diff.where(diff > 0, 0).rolling(14).mean()
        down = (-diff.where(diff < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (up / (down + 1e-10))))
        curr_rsi = rsi.iloc[-1]

        # 지표 계산 (5일선, 볼밴, MACD)
        ma5 = c.rolling(5).mean().iloc[-1]
        ma20 = c.rolling(20).mean()
        std20 = c.rolling(20).std()
        bbu, bbl = (ma20 + (std20 * 2)).iloc[-1], (ma20 - (std20 * 2)).iloc[-1]
        ema12, ema26 = c.ewm(span=12).mean(), c.ewm(span=26).mean()
        macd = ema12 - ema26
        curr_macd, prev_macd = macd.iloc[-1], macd.iloc[-2]

        # 매수 판정 (RSI <= 45 & 2개 이상)
        if curr_rsi <= 45 and (market_type == "코인" or curr_price < prev_close):
            cond = []
            if curr_price <= ma5: cond.append("1")
            if curr_price <= bbl * 1.05: cond.append("2")
            if curr_macd > prev_macd: cond.append("3")
            if len(cond) >= 2:
                send_alert(f"🟢[{market_type}] {name} {curr_rsi:.0f} ({','.join(cond)})")

        # 매도 판정 (RSI >= 55 & 2개 이상)
        elif curr_rsi >= 55 and (market_type == "코인" or curr_price > prev_close):
            m_cond = []
            if curr_price >= ma5: m_cond.append("1")
            if curr_price >= bbu * 0.95: m_cond.append("2")
            if curr_macd < prev_macd: m_cond.append("3")
            if len(m_cond) >= 2:
                send_alert(f"🔴[{market_type}] {name} {curr_rsi:.0f} ({','.join(m_cond)})")
    except: pass

def run_loop():
    send_alert("🚀 [전략 가동] 실시간 스캔 및 응답 모드 시작")
    start_time = time.time()
    
    while True:
        if time.time() - start_time > 20000: break # 5.5시간 후 종료

        check_status_request() # 텔레그램 질문 확인

        now = datetime.now(pytz.timezone('Asia/Seoul'))
        curr_time = int(now.strftime('%H%M'))
        is_weekday = now.weekday() < 5

        # 1. 코인 (상위 10개)
        try:
            for t in pyupbit.get_tickers(fiat="KRW")[:10]:
                analyze(pyupbit.get_ohlcv(t, interval="minute1", count=50), t.split("-")[1], "코인")
        except: pass

        # 2. 국장 (코스피 시총 상위 50개)
        if is_weekday and 900 <= curr_time <= 1530:
            try:
                kospi = fdr.StockListing('KOSPI').sort_values('Marcap', ascending=False).head(50)
                for _, r in kospi.iterrows():
                    analyze(fdr.DataReader(r['Code']).tail(50), r['Name'], "국장")
                    time.sleep(0.05)
            except: pass
        
        # 3. 미국 주식 (S&P500 상위 100개)
        if is_weekday and (curr_time >= 2230 or curr_time <= 500):
            try:
                us = fdr.StockListing('S&P500').head(100)
                for _, r in us.iterrows():
                    analyze(fdr.DataReader(r['Symbol']).tail(50), r['Symbol'], "미장")
                    time.sleep(0.05)
            except: pass

        time.sleep(60)

if __name__ == "__main__":
    run_loop()
