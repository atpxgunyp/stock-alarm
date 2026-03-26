import FinanceDataReader as fdr
import pandas_ta as ta
import os, requests, pytz
from datetime import datetime

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def send_alert(message):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": CHAT_ID, "text": message})
    except: pass

def get_market():
    seoul_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_tz)
    if now.weekday() >= 5: return "OFF"
    curr = now.hour * 100 + now.minute
    if 900 <= curr <= 1540: return "KOREA"
    if curr >= 2230 or curr <= 500: return "USA"
    return "WAIT"

def scan(m_type):
    try:
        if m_type == "KOREA":
            # 한국 상위 100종목 (시총 순)
            stocks = fdr.StockListing('KRX').sort_values('Marcap', ascending=False).head(100)
            s_col, n_col = 'Code', 'Name'
        else:
            # 미국 S&P500 상위 100종목
            stocks = fdr.StockListing('S&P500').head(100)
            s_col, n_col = 'Symbol', 'Symbol'

        for _, row in stocks.iterrows():
            try:
                symbol, name = row[s_col], row[n_col]
                df = fdr.DataReader(symbol).tail(35)
                if len(df) < 20: continue
                
                rsi = ta.rsi(df['Close'], length=14).iloc[-1]
                curr_price = df['Close'].iloc[-1]
                
                if rsi < 30:
                    send_alert(f"🟢 [매수포착] {name}\n가격: {curr_price:,}\nRSI: {rsi:.2f}")
                elif rsi > 70:
                    send_alert(f"🔴 [매도포착] {name}\n가격: {curr_price:,}\nRSI: {rsi:.2f}")
            except: continue
    except: pass

if __name__ == "__main__":
    m = get_market()
    # 장이 열려 있을 때만 스캔을 실행 (불필요한 인사말 삭제됨)
    if m in ["KOREA", "USA"]:
        scan(m)
