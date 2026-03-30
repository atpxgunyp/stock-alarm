import FinanceDataReader as fdr
import pyupbit
import os, requests, pytz, time
from datetime import datetime

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 상태 관리를 위한 변수들
last_msg_id = 0
alert_count = {}  # { '삼성전자': 3, 'BTC': 1 } 식으로 횟수 저장
last_date = ""    # 날짜 변경 감지용

def send_alert(msg):
    if not (TOKEN and CHAT_ID): return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except: pass

def check_status_request():
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
                send_alert(f"✅ 정상 가동 중!\n🕒 {now.strftime('%H:%M:%S')}\n📊 종목당 일일 최대 3회 제한 적용 중")
                last_msg_id = msg_id
    except: pass

def analyze(df, name, market_type):
    global alert_count
    try:
        # 하루 3회 제한 체크
        current_count = alert_count.get(name, 0)
        if current_count >= 3:
            return # 3번 넘었으면 분석 패스

        if df is None or len(df) < 35: return
        c = df['Close']
        prev_close, curr_price = c.iloc[-2], c.iloc[-1]
        
        # 지표 계산 (RSI 45/55, MA5, BB, MACD)
        diff = c.diff()
        up = diff.where(diff > 0, 0).rolling(14).mean()
        down = (-diff.where(diff < 0, 0)).rolling(14).mean()
        rsi = (100 - (100 / (1 + (up / (down + 1e-10))))).iloc[-1]

        ma5 = c.rolling(5).mean().iloc[-1]
        ma20 = c.rolling(20).mean()
        std20 = c.rolling(20).std()
        bbu, bbl = (ma20 + (std20 * 2)).iloc[-1], (ma20 - (std20 * 2)).iloc[-1]
        ema12, ema26 = c.ewm(span=12).mean(), c.ewm(span=26).mean()
        macd = ema12 - ema26
        curr_macd, prev_macd = macd.iloc[-1], macd.iloc[-2]

        # 매수/매도 로직
        is_hit = False
        msg = ""

        if rsi <= 45 and (market_type == "코인" or curr_price < prev_close):
            cond = []
            if curr_price <= ma5: cond.append("1")
            if curr_price <= bbl * 1.05: cond.append("2")
            if curr_macd > prev_macd: cond.append("3")
            if len(cond) >= 2:
                msg = f"🟢[{market_type}] {name} {rsi:.0f} ({','.join(cond)}) [{current_count+1}/3]"
                is_hit = True

        elif rsi >= 55 and (market_type == "코인" or curr_price > prev_close):
            m_cond = []
            if curr_price >= ma5: m_cond.append("1")
            if curr_price >= bbu * 0.95: m_cond.append("2")
            if curr_macd < prev_macd: m_cond.append("3")
            if len(m_cond) >= 2:
                msg = f"🔴[{market_type}] {name} {rsi:.0f} ({','.join(m_cond)}) [{current_count+1}/3]"
                is_hit = True

        if is_hit:
            send_alert(msg)
            alert_count[name] = current_count + 1 # 횟수 증가
    except: pass

def run_loop():
    global alert_count, last_date
    send_alert("🚀 [전략 가동] 종목별 3회 제한 모드 시작")
    start_time = time.time()
    
    while True:
        if time.time() - start_time > 20000: break

        KST = pytz.timezone('Asia/Seoul')
        now = datetime.now(KST)
        curr_date = now.strftime('%Y%m%d')
        curr_time = int(now.strftime('%H%M'))

        # 날짜가 바뀌면 횟수 초기화
        if curr_date != last_date:
            alert_count = {}
            last_date = curr_date
            print(f"{curr_date} 새로운 날짜 - 알림 횟수 초기화 완료")

        check_status_request()

        # 1. 코인
        try:
            for t in pyupbit.get_tickers(fiat="KRW")[:10]:
                analyze(pyupbit.get_ohlcv(t, interval="minute1", count=50), t.split("-")[1], "코인")
        except: pass

        # 2. 국장 (코스피 50)
        if (now.weekday() < 5) and 900 <= curr_time <= 1530:
            try:
                kospi = fdr.StockListing('KOSPI').sort_values('Marcap', ascending=False).head(50)
                for _, r in kospi.iterrows():
                    analyze(fdr.DataReader(r['Code']).tail(50), r['Name'], "국장")
                    time.sleep(0.05)
            except: pass
        
        # 3. 미장 (S&P 100)
        if (now.weekday() < 5) and (curr_time >= 2230 or curr_time <= 500):
            try:
                us = fdr.StockListing('S&P500').head(100)
                for _, r in us.iterrows():
                    analyze(fdr.DataReader(r['Symbol']).tail(50), r['Symbol'], "미장")
                    time.sleep(0.05)
            except: pass

        time.sleep(60)

if __name__ == "__main__":
    run_loop()
