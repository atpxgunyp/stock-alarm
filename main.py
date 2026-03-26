import FinanceDataReader as fdr
import pandas_ta as ta
import os, requests, pytz
from datetime import datetime

# 설정값 가져오기
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def send_alert(message):
    if not TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
    except:
        pass

def get_market():
    seoul_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_tz)
    if now.weekday() >= 5: return "OFF"
    curr = now.hour * 100 + now.minute
    if 900 <= curr <= 1540: return "KOREA"
    if curr >= 2230 or curr <= 500: return "USA"
    return "WAIT"

def scan(m_type):
    send_alert(f"🚀 {m_type} 시장 감시 시작")
    try:
        # 상위 30개만 가볍게 스캔 (에러 방지용)
        if m_type == "KOREA":
            stocks = fdr.StockListing('KRX').head(30)
            s_col, n_col = 'Code', 'Name'
        else:
            stocks = fdr.StockListing('S&P500').head(30)
            s_col, n_col = 'Symbol', 'Symbol'

        for _, row in stocks.iterrows():
            try:
                symbol, name = row[s_col], row[n_col]
                df = fdr.DataReader(symbol).tail(30)
                if len(df) < 20: continue
                
                rsi = ta.rsi(df['Close'], length=14).iloc[-1]
                ma5 = ta.sma(df['Close'], length=5).iloc[-1]
                curr_price = df['Close'].iloc[-1]
                
                if rsi < 35:
                    send_alert(f"🟢 [과매도] {name}\n가격: {curr_price:,}\nRSI: {rsi:.2f}")
                elif rsi > 75:
                    send_alert(f"🔴 [과매수] {name}\n가격: {curr_price:,}\nRSI: {rsi:.2f}")
            except:
                continue
    except Exception as e:
        send_alert(f"❌ 에러 발생: {str(e)}")

if __name__ == "__main__":
    send_alert("🤖 봇이 깨어났습니다.")
    m = get_market()
    if m in ["KOREA", "USA"]:
        scan(m)
    else:
        send_alert(f"💤 현재는 대기 시간입니다. (상태: {m})")
