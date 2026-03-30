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
    except Exception as e:
        print(f"텔레그램 발송 실패: {e}")

def analyze(df, name, market_type):
    # (RSI 필수 + 2개 이상 조건 로직은 동일)
    try:
        if df is None or len(df) < 35: return
        c = df['Close']
        # ... (중략: RSI, MA5, BB, MACD 계산 로직) ...
        # (앞서 드린 analyze 함수 내용 그대로 넣으시면 됩니다)
    except: pass

def run_loop():
    print("시스템 가동 시작...")
    send_alert("🚀 [실시간 모니터링] 감시를 시작합니다. (종료 시까지 무한 반복)")
    
    start_time = time.time()
    
    while True:
        # 5시간 30분 지나면 안전하게 종료 (GitHub 6시간 제한 대비)
        if time.time() - start_time > 20000:
            print("재시작을 위해 루프 종료")
            break

        # 한국 시간 강제 설정
        KST = pytz.timezone('Asia/Seoul')
        now = datetime.now(KST)
        curr_time = int(now.strftime('%H%M')) # 예: 10시 55분 -> 1055
        is_weekday = now.weekday() < 5

        print(f"현재 시각(KST): {now.strftime('%Y-%m-%d %H:%M:%S')} | 상태: 스캔 중")

        # 1. 코인 (24시간)
        try:
            coins = pyupbit.get_tickers(fiat="KRW")[:10]
            for t in coins:
                analyze(pyupbit.get_ohlcv(t, interval="minute1", count=50), t.split("-")[1], "코인")
        except Exception as e:
            print(f"코인 에러: {e}")

        # 2. 한국 주식 (09:00 ~ 15:30)
        if is_weekday and 900 <= curr_time <= 1530:
            print(">>> 한국 시장 스캔 실행 중")
            try:
                krx = fdr.StockListing('KRX').sort_values('Marcap', ascending=False).head(100)
                for _, r in krx.iterrows():
                    analyze(fdr.DataReader(r['Code']).tail(50), r['Name'], "국장")
            except Exception as e:
                print(f"국장 에러: {e}")
        
        # 3. 미국 주식 (22:30 ~ 05:00)
        if is_weekday and (curr_time >= 2230 or curr_time <= 500):
            print(">>> 미국 시장 스캔 실행 중")
            try:
                us = fdr.StockListing('S&P500').head(100)
                for _, r in us.iterrows():
                    analyze(fdr.DataReader(r['Symbol']).tail(50), r['Symbol'], "미장")
            except Exception as e:
                print(f"미장 에러: {e}")

        print("1분 대기 후 재스캔...")
        time.sleep(60)

if __name__ == "__main__":
    run_loop()
