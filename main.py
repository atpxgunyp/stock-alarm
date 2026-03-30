import FinanceDataReader as fdr
import pyupbit
import os, requests, pytz, time
from datetime import datetime

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 마지막으로 응답한 메시지 ID를 저장 (중복 응답 방지)
last_msg_id = 0

def send_alert(msg):
    if not (TOKEN and CHAT_ID): return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except: pass

def check_status_request():
    """텔레그램 메시지를 확인하여 '작동?' 질문에 답장함"""
    global last_msg_id
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        params = {"offset": -1, "timeout": 5} # 가장 최근 메시지만 가져옴
        response = requests.get(url, params=params).json()
        
        if response.get("ok") and response.get("result"):
            last_update = response["result"][-1]
            msg_text = last_update.get("message", {}).get("text", "")
            msg_id = last_update.get("update_id")

            if ("작동?" in msg_text or "상태?" in msg_text) and msg_id != last_msg_id:
                now = datetime.now(pytz.timezone('Asia/Seoul'))
                status_msg = f"✅ 현재 정상 가동 중입니다!\n🕒 확인 시각: {now.strftime('%H:%M:%S')}\n📊 감시 대상: 코스피 50 / 미장 / 코인"
                send_alert(status_msg)
                last_msg_id = msg_id # 응답 완료 처리
    except: pass

# ... (analyze 함수는 이전과 동일) ...

def run_loop():
    send_alert("🚀 [전략 가동] 실시간 감시 및 상태 응답 모드 시작")
    start_time = time.time()
    
    while True:
        if time.time() - start_time > 20000: break

        # 1. 사용자 질문("작동?") 확인 및 응답
        check_status_request()

        KST = pytz.timezone('Asia/Seoul')
        now = datetime.now(KST)
        curr_time = int(now.strftime('%H%M'))
        is_weekday = now.weekday() < 5

        # 2. 시장별 스캔 실행 (코인, 국장, 미장)
        # (기존 스캔 로직 그대로 유지)
        try:
            # 코인 스캔... (생략)
            if is_weekday and 900 <= curr_time <= 1530:
                # 국장 스캔... (생략)
            # 미장 스캔... (생략)
        except: pass

        time.sleep(30) # 응답 속도를 위해 30초 간격으로 단축 가능
