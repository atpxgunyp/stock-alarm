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

def get_market_status():
    seoul_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_tz)
    if now.weekday() >= 5: return "OFF"
    
    curr = now.hour * 100 + now.minute
    
    # 한국 시장 체크
    if 900 <= curr <= 1540: return "KOREA"
    if 1541 <= curr <= 1605: return "KOREA_DONE" # 장 마감 직후
    
    # 미국 시장 체크 (서머타임 미고려 기준, 필요 시 시간 조정 가능)
    if curr >= 2230 or curr <= 500: return "USA"
    if 501 <= curr <= 535: return "USA_DONE" # 장 마감 직후
    
    return "WAIT"

def scan(m_type):
    try:
        if m_type == "KOREA":
            stocks = fdr.StockListing('KRX').sort_values('Marcap', ascending=False).head(100)
            s_col, n_col = 'Code', 'Name'
        else:
            stocks = fdr.StockListing('S&P500').head(100)
            s_col, n_col = 'Symbol', 'Symbol'

        for _, row in stocks.iterrows():
            try:
                symbol, name = row[s_col], row[n_col]
                df = fdr.DataReader(symbol).tail(60)
                if len(df) < 30: continue
                
                curr_p = df['Close'].iloc[-1]
                prev_p = df['Close'].iloc[-2]
                rsi = ta.rsi(df['Close'], length=14).iloc[-1]
                bb = ta.bbands(df['Close'], length=20, std=2)
                macd_df = ta.macd(df['Close'])
                ma5 = ta.sma(df['Close'], length=5).iloc[-1]
                
                conditions = []

                # 매수 분석
                if rsi < 40 and curr_p < prev_p:
                    if curr_p > ma5: conditions.append("✅ 5일선 돌파")
                    if curr_p < bb['BBL_20_2.0'].iloc[-1] * 1.02: conditions.append("✅ 볼린저 하단")
                    if macd_df['MACD_12_26_9'].iloc[-1] > macd_df['MACDs_12_26_9'].iloc[-1]: conditions.append("✅ MACD 골든크로스")
                    if conditions:
                        diff = ((curr_p - prev_p) / prev_p) * 100
                        send_alert(f"🟢 [매수포착] {name}\n현재가: {curr_p:,} ({diff:.2f}%)\n전일종가: {prev_p:,}\nRSI: {rsi:.1f}\n" + "\n".join(conditions))

                # 매도 분석
                elif rsi > 60 and curr_p > prev_p:
                    if curr_p < ma5: conditions.append("❌ 5일선 하회")
                    if curr_p > bb['BBU_20_2.0'].iloc[-1] * 0.98: conditions.append("❌ 볼린저 상단")
                    if macd_df['MACD_12_26_9'].iloc[-1] < macd_df['MACDs_12_26_9'].iloc[-1]: conditions.append("❌ MACD 데드크로스")
                    if conditions:
                        diff = ((curr_p - prev_p) / prev_p) * 100
                        send_alert(f"🔴 [매도포착] {name}\n현재가: {curr_p:,} (+{diff:.2f}%)\n전일종가: {prev_p:,}\nRSI: {rsi:.1f}\n" + "\n".join(conditions))
            except: continue
    except: pass

if __name__ == "__main__":
    status = get_market_status()
    today_str = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')
    
    if status == "KOREA":
        scan("KOREA")
    elif status == "KOREA_DONE":
        send_alert(f"🏁 [{today_str}] 한국 주식 시장 마감되었습니다.")
    elif status == "USA":
        scan("USA")
    elif status == "USA_DONE":
        send_alert(f"🏁 [{today_str}] 미국 주식 시장 마감되었습니다.")
