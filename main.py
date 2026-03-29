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
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except:
        pass

def get_market_status():
    seoul_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_tz)
    if now.weekday() >= 5: return "OFF"
    curr = now.hour * 100 + now.minute
    if 900 <= curr <= 1540: return "KOREA"
    if 1541 <= curr <= 1640: return "KOREA_DONE"
    if curr >= 2230 or curr <= 500: return "USA"
    if 501 <= curr <= 600: return "USA_DONE"
    return "WAIT"

def analyze_logic(df, name, is_coin=False):
    try:
        # 데이터 유효성 검사 (최소 50개 확보)
        if df is None or len(df) < 50: return
        
        # 지표 계산
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.sma(length=5, append=True)

        # 계산된 지표 컬럼 찾기 (대소문자 구분 없이)
        rsi_col = [c for c in df.columns if 'RSI' in c.upper()]
        lbb_col = [c for c in df.columns if 'BBL' in c.upper()]
        ubb_col = [c for c in df.columns if 'BBU' in c.upper()]
        macd_col = [c for c in df.columns if 'MACD' in c.upper() and 'S' not in c.upper()]
        sig_col = [c for c in df.columns if 'MACDS' in c.upper()]
        ma5_col = [c for c in df.columns if 'SMA_5' in c.upper()]

        if not (rsi_col and lbb_col and ubb_col and macd_col and sig_col and ma5_col): return

        curr_p, prev_p = df['Close'].iloc[-1], df['Close'].iloc[-2]
        curr_rsi = df[rsi_col[0]].iloc[-1]
        
        conds = []
        # 매수 조건 (RSI 45 미만 + 하락 중)
        if curr_rsi < 45 and curr_p < prev_p:
            if curr_p > df[ma5_col[0]].iloc[-1] * 0.97: conds.append("✅ 5일선 근접/돌파")
            if curr_p < df[lbb_col[0]].iloc[-1] * 1.07: conds.append("✅ 볼린저 하단영역")
            if df[macd_col[0]].iloc[-1] > df[sig_col[0]].iloc[-1]: conds.append("✅ MACD 우상향")
            if conds:
                tag = "🪙 [코인매수]" if is_coin else "🟢 [주식매수]"
                send_alert(f"{tag} {name}\n가: {curr_p:,.0f}\nRSI: {curr_rsi:.1f}\n" + "\n".join(conds))

        # 매도 조건 (RSI 55 초과 + 상승 중)
        elif curr_rsi > 55 and curr_p > prev_p:
            if curr_p < df[ma5_col[0]].iloc[-1] * 1.03: conds.append("❌ 5일선 이탈징후")
            if curr_p > df[ubb_col[0]].iloc[-1] * 0.93: conds.append("❌ 볼린저 상단영역")
            if df[macd_col[0]].iloc[-1] < df[sig_col[0]].iloc[-1]: conds.append("❌ MACD 우하향")
            if conds:
                tag = "🪙 [코인매도]" if is_coin else "🔴 [주식매도]"
                send_alert(f"{tag} {name}\n가: {curr_p:,.0f}\nRSI: {curr_rsi:.1f}\n" + "\n".join(conds))
    except:
        pass

def scan_stocks(m_type):
    try:
        if m_type == "KOREA":
            stocks = fdr.StockListing('KRX').sort_values('Marcap', ascending=False).head(100)
            for _, row in stocks.iterrows():
                try:
                    df = fdr.DataReader(row['Code']).tail(100)
                    analyze_logic(df, row['Name'])
                    time.sleep(0.1)
                except: continue
        else:
            stocks = fdr.StockListing('S&P500').head(100)
            for _, row in stocks.iterrows():
                try:
                    df = fdr.DataReader(row['Symbol']).tail(100)
                    analyze_logic(df, row['Symbol'])
                    time.sleep(0.1)
                except: continue
    except: pass

def scan_coins():
    tickers = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-ADA", "KRW-DOGE", "KRW-DOT", "KRW-TRX", "KRW-AVAX", "KRW-LINK"]
    for t in tickers:
        try:
            df = pyupbit.get_ohlcv(t, interval="day", count=100)
            if df is not None:
                analyze_logic(df, t.replace("KRW-",""), is_coin=True)
            time.sleep(0.1)
        except: continue

if __name__ == "__main__":
    scan_coins()
    status = get_market_status()
    if status in ["KOREA", "USA"]:
        scan_stocks(status)
    elif "_DONE" in status:
        m = "한국" if "KOREA" in status else "미국"
        send_alert(f"🏁 {m} 시장 마감되었습니다.")
