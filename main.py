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

def get_market_status():
    seoul_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_tz)
    curr = now.hour * 100 + now.minute
    
    # 주말 여부 확인 (주식용)
    is_weekend = now.weekday() >= 5
    
    status = "WAIT"
    if not is_weekend:
        if 900 <= curr <= 1540: status = "KOREA"
        elif 1541 <= curr <= 1640: status = "KOREA_DONE" 
        elif curr >= 2230 or curr <= 500: status = "USA"
        elif 501 <= curr <= 600: status = "USA_DONE" 
    
    return status

def analyze_logic(df, name, symbol, is_coin=False):
    """주식과 코인 공통으로 사용하는 널널한 분석 로직"""
    try:
        curr_p, prev_p = df['Close'].iloc[-1], df['Close'].iloc[-2]
        rsi = ta.rsi(df['Close'], length=14).iloc[-1]
        bb = ta.bbands(df['Close'], length=20, std=2)
        macd_df = ta.macd(df['Close'])
        ma5 = ta.sma(df['Close'], length=5).iloc[-1]
        
        conds = []
        prefix = "🪙 [코인" if is_coin else "🟢 [주식"
        
        # 매수 조건 (RSI 45 미만 + 하락 중)
        if rsi < 45 and curr_p < prev_p:
            if curr_p > ma5 * 0.97: conds.append("✅ 5일선 근접/돌파")
            if curr_p < bb['BBL_20_2.0'].iloc[-1] * 1.07: conds.append("✅ 볼린저 하단영역")
            if macd_df['MACD_12_26_9'].iloc[-1] > macd_df['MACDs_12_26_9'].iloc[-1]: conds.append("✅ MACD 우상향")
            
            if conds:
                diff = ((curr_p - prev_p) / prev_p) * 100
                send_alert(f"{prefix}매수] {name}\n가: {curr_p:,}\nRSI: {rsi:.1f}\n" + "\n".join(conds))

        # 매도 조건 (RSI 55 초과 + 상승 중)
        elif rsi > 55 and curr_p > prev_p:
            prefix = "🪙 [코인" if is_coin else "🔴 [주식"
            if curr_p < ma5 * 1.03: conds.append("❌ 5일선 이탈징후")
            if curr_p > bb['BBU_20_2.0'].iloc[-1] * 0.93: conds.append("❌ 볼린저 상단영역")
            if macd_df['MACD_12_26_9'].iloc[-1] < macd_df['MACDs_12_26_9'].iloc[-1]: conds.append("❌ MACD 우하향")
            
            if conds:
                diff = ((curr_p - prev_p) / prev_p) * 100
                send_alert(f"{prefix}매도] {name}\n가: {curr_p:,}\nRSI: {rsi:.1f}\n" + "\n".join(conds))
    except: pass

def scan_stocks(m_type):
    if m_type == "KOREA":
        stocks = fdr.StockListing('KRX').sort_values('Marcap', ascending=False).head(100)
        s_col, n_col = 'Code', 'Name'
    else:
        stocks = fdr.StockListing('S&P500').head(100)
        s_col, n_col = 'Symbol', 'Symbol'

    for _, row in stocks.iterrows():
        df = fdr.DataReader(row[s_col]).tail(60)
        if len(df) >= 30: analyze_logic(df, row[n_col], row[s_col])

def scan_coins():
    # 업비트 주요 코인 10개 (비트, 이더, 리플, 솔라나 등)
    tickers = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-ADA", "KRW-DOGE", "KRW-DOT", "KRW-TRX", "KRW-AVAX", "KRW-LINK"]
    for ticker in tickers:
        df = pyupbit.get_ohlcv(ticker, interval="day", count=60)
        if df is not None: analyze_logic(df, ticker.replace("KRW-", ""), ticker, is_coin=True)

if __name__ == "__main__":
    # 1. 코인은 언제나 스캔 (365일 30분마다)
    scan_coins()
    
    # 2. 주식은 장 상황에 맞춰 스캔
    status = get_market_status()
    if status in ["KOREA", "USA"]: scan_stocks(status)
    elif "_DONE" in status:
        today = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')
        m_name = "한국" if "KOREA" in status else "미국"
        send_alert(f"🏁 [{today}] {m_name} 시장 마감되었습니다.")
