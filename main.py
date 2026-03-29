import FinanceDataReader as fdr
import pandas_ta as ta
import pyupbit
import os, requests, pytz, time
from datetime import datetime

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def send_alert(message):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": CHAT_ID, "text": message})
    except: pass

def check_status_reply():
    """최근 30분 내 '작동' 메시지에 응답"""
    if not TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        res = requests.get(url).json()
        if res.get("result"):
            last_msg = res["result"][-1].get("message", {})
            text, msg_date = last_msg.get("text", ""), last_msg.get("date", 0)
            if "작동" in text and (time.time() - msg_date < 1800):
                now = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%H:%M:%S')
                send_alert(f"✅ 봇 정상 작동 중!\n확인 시간: {now}\n(주식+코인 널널한 조건 감시 중)")
    except: pass

def get_market_status():
    seoul_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_tz)
    curr = now.hour * 100 + now.minute
    if now.weekday() >= 5: return "OFF" # 주말엔 주식스캔 OFF
    if 900 <= curr <= 1540: return "KOREA"
    if 1541 <= curr <= 1640: return "KOREA_DONE"
    if curr >= 2230 or curr <= 500: return "USA"
    if 501 <= curr <= 600: return "USA_DONE"
    return "WAIT"

def analyze_logic(df, name, is_coin=False):
    """최종 확정된 널널한 분석 로직"""
    try:
        curr_p, prev_p = df['Close'].iloc[-1], df['Close'].iloc[-2]
        rsi = ta.rsi(df['Close'], length=14).iloc[-1]
        bb = ta.bbands(df['Close'], length=20, std=2)
        macd = ta.macd(df['Close'])
        ma5 = ta.sma(df['Close'], length=5).iloc[-1]
        
        conds = []
        # 매수: RSI 45미만 + 전일비 하락 + (5일선 3%내/BB 7%내/MACD 우상향 중 1개)
        if rsi < 45 and curr_p < prev_p:
            if curr_p > ma5 * 0.97: conds.append("✅ 5일선 근접/돌파")
            if curr_p < bb['BBL_20_2.0'].iloc[-1] * 1.07: conds.append("✅ 볼린저 하단영역")
            if macd['MACD_12_26_9'].iloc[-1] > macd['MACDs_12_26_9'].iloc[-1]: conds.append("✅ MACD 우상향")
            if conds:
                tag = "🪙 [코인매수]" if is_coin else "🟢 [주식매수]"
                send_alert(f"{tag} {name}\n가: {curr_p:,}\nRSI: {rsi:.1f}\n" + "\n".join(conds))

        # 매도: RSI 55초과 + 전일비 상승 + (5일선 3%내/BB 7%내/MACD 우하향 중 1개)
        elif rsi > 55 and curr_p > prev_p:
            if curr_p < ma5 * 1.03: conds.append("❌ 5일선 이탈징후")
            if curr_p > bb['BBU_20_2.0'].iloc[-1] * 0.93: conds.append("❌ 볼린저 상단영역")
            if macd['MACD_12_26_9'].iloc[-1] < macd['MACDs_12_26_9'].iloc[-1]: conds.append("❌ MACD 우하향")
            if conds:
                tag = "🪙 [코인매도]" if is_coin else "🔴 [주식매도]"
                send_alert(f"{tag} {name}\n가: {curr_p:,}\nRSI: {rsi:.1f}\n" + "\n".join(conds))
    except: pass

def scan_stocks(m_type):
    if m_type == "KOREA":
        stocks = fdr.StockListing('KRX').sort_values('Marcap', ascending=False).head(100)
        s_col, n_col = 'Code', 'Name'
    else:
        stocks = fdr.StockListing('S&P500').head(100)
        s_col, n_col = 'Symbol', 'Symbol'
    for _, row in stocks.iterrows():
        try:
            df = fdr.DataReader(row[s_col]).tail(60)
            if len(df) >= 30: analyze_logic(df, row[n_col])
        except: continue

def scan_coins():
    tickers = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-ADA", "KRW-DOGE", "KRW-DOT", "KRW-TRX", "KRW-AVAX", "KRW-LINK"]
    for t in tickers:
        try:
            df = pyupbit.get_ohlcv(t, interval="day", count=60)
            if df is not None: analyze_logic(df, t.replace("KRW-",""), is_coin=True)
        except: continue

if __name__ == "__main__":
    check_status_reply()
    scan_coins() # 코인은 언제나 실행
    status = get_market_status()
    if status in ["KOREA", "USA"]: scan_stocks(status)
    elif "_DONE" in status:
        m = "한국" if "KOREA" in status else "미국"
        send_alert(f"🏁 {m} 시장 마감되었습니다.")
