import FinanceDataReader as fdr
import pandas_ta as ta
import os, asyncio, pytz
from datetime import datetime
from telegram import Bot

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
bot = Bot(token=TOKEN)

async def send_alert(message):
    try: await bot.send_message(chat_id=CHAT_ID, text=message)
    except: pass

def get_market():
    seoul_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_tz)
    if now.weekday() >= 5: return "OFF"
    curr = now.hour * 100 + now.minute
    if 900 <= curr <= 1540: return "KOREA"
    if curr >= 2230 or curr <= 500: return "USA"
    return "WAIT"

async def scan(m_type):
    await send_alert(f"🚀 {m_type} 시장 감시를 시작합니다!")
    if m_type == "KOREA":
        stocks = fdr.StockListing('KRX').sort_values('Marcap', ascending=False).head(100)
        s_col, n_col = 'Code', 'Name'
    else:
        stocks = fdr.StockListing('S&P500').head(100)
        s_col, n_col = 'Symbol', 'Symbol'

    for _, row in stocks.iterrows():
        try:
            symbol, name = row[s_col], row[n_col]
            df = fdr.DataReader(symbol).tail(50)
            df['RSI'] = ta.rsi(df['Close'], length=14)
            bb = ta.bbands(df['Close'], length=20, std=2)
            df['MACD'] = ta.macd(df['Close'])['MACD_12_26_9']
            df['MA5'] = ta.sma(df['Close'], length=5)
            c, p = df.iloc[-1], df.iloc[-2]
            
            b_score = (1 if c['RSI']<45 else 0) + (1 if c['Close']<bb['BBL_20_2.0'].iloc[-1]*1.02 else 0) + (1 if c['MACD']>p['MACD'] else 0) + (1 if c['Close']>c['MA5'] else 0)
            s_score = (1 if c['RSI']>65 else 0) + (1 if c['Close']>bb['BBU_20_2.0'].iloc[-1]*0.98 else 0) + (1 if c['MACD']<p['MACD'] else 0) + (1 if c['Close']<c['MA5'] else 0)

            if b_score >= 3: await send_alert(f"🟢 [구매] {name}\n가격: {c['Close']:,}\n점수: {b_score}/4")
            elif s_score >= 3: await send_alert(f"🔴 [판매] {name}\n가격: {c['Close']:,}\n점수: {s_score}/4")
        except: continue

async def main():
    await send_alert("🤖 주식 봇 가동!")
    m = get_market()
    if m in ["KOREA", "USA"]: await scan(m)
    else: await send_alert(f"💤 장 대기 중 (상태: {m})")

if __name__ == "__main__":
    asyncio.run(main())
