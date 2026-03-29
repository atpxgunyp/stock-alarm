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
        if df is None or len(df) < 40: return
        
        close = df['Close']
        rsi = ta.rsi(close, length=14)
        bb = ta.bbands(close, length=20, std=2)
        macd = ta.macd(close)
        ma5 = ta.sma(close, length=5)

        if rsi is None or bb is None or macd is None or ma5 is None: return

        curr_p, prev_p = close.iloc[-1], close.iloc[-2]
        curr_rsi = rsi.iloc[-1]
        
        lbb_list = [c for c in bb.columns if 'BBL' in c]
        ubb_list = [c for c in bb.columns if 'BBU' in c]
        macd_list = [c for c in macd.columns if 'MACD_' in c and 's' not in c]
        sig_list = [c for c in macd.columns if 'MACDs_' in c]

        if not (lbb_list and ubb_list and macd_list and sig_list): return

        conds = []
        if curr_rsi < 45 and curr_p < prev_p:
            if curr_p > ma5.iloc[-1] * 0.97: conds.append("✅ 5일선 근접/돌파")
            if curr_p < bb[lbb_list[0]].iloc[-1] * 1.07: conds.append("✅ 볼린저 하단영역")
            if macd[macd_list[0]].iloc[-1] > macd[sig_list[0]].iloc[-1]: conds.append("✅ MACD 우상향")
            if conds:
                tag = "🪙 [코인매수]" if is_coin else "🟢 [주식매수]"
                send_alert(f"{tag} {name}\n가: {curr_p:,.0f}\nRSI: {curr_rsi:.1f}\n" + "\n".join(conds))

        elif curr_rsi > 55 and curr_p > prev_p:
            if curr_p < ma5.iloc[-1] * 1.03: conds.append("❌ 5일선 이탈징후")
            if curr_p > bb[ubb_list[0]].iloc[-1] * 0.93: conds.append("❌ 볼린저 상단영역")
            if macd[macd_list[0]].iloc[-1] < macd[sig_list[0]].iloc[-1]: conds.append("❌ MACD 우하향")
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
                    df = fdr.DataReader(row['Code']).tail(60)
                    analyze_logic(df, row['Name'])
                    time.sleep(0.1)
                except: continue
        else:
            stocks = fdr.StockListing('S&P500').head(100)
            for _, row in stocks.iterrows():
                try:
                    df = fdr.DataReader(row['Symbol']).tail(60)
                    analyze_logic(df, row['Symbol'])
                    time.sleep(0.1)
                except: continue
    except: pass

def scan_coins():
    tickers = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-ADA", "KRW-DOGE", "KRW-DOT", "KRW-TRX", "KRW-AVAX", "KRW-LINK"]
    for t in tickers:
        try:
            df = pyupbit.get_ohlcv(t, interval="day", count=60)
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
