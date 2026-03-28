# ... (상단 생략: 기존 import 및 설정 동일)

def scan(m_type):
    try:
        # (생략: 종목 리스트 불러오기 동일)

        for _, row in stocks.iterrows():
            try:
                # ... (생략: 데이터 로드 및 지표 계산 동일)
                
                conditions = []
                
                # --- 널널해진 기술적 지표 판정 로직 ---

                # [매수 판정] RSI 45 미만 + 전일보다 하락했을 때
                if rsi < 45 and curr_p < prev_p:
                    # 1. 5일선: 돌파했거나, 5일선과의 차이가 3% 이내일 때 (근접)
                    if curr_p > ma5 * 0.97: 
                        conditions.append("✅ 5일선 근접/돌파")
                    
                    # 2. 볼린저밴드: 하단선보다 7% 높은 곳까지 허용 (범위 확대)
                    if curr_p < bb['BBL_20_2.0'].iloc[-1] * 1.07: 
                        conditions.append("✅ 볼린저 하단 영역")
                    
                    # 3. MACD: 골든크로스 혹은 MACD선이 시그널선보다 위에 있기만 하면 허용
                    if macd_df['MACD_12_26_9'].iloc[-1] > macd_df['MACDs_12_26_9'].iloc[-1]:
                        conditions.append("✅ MACD 우상향")

                    if conditions:
                        diff = ((curr_p - prev_p) / prev_p) * 100
                        send_alert(f"🟢 [매수포착] {name}\n가: {curr_p:,} ({diff:.2f}%)\nRSI: {rsi:.1f}\n" + "\n".join(conditions))

                # [매도 판정] RSI 55 초과 + 전일보다 상승했을 때
                elif rsi > 55 and curr_p > prev_p:
                    # 1. 5일선: 선 아래로 떨어졌거나, 5일선보다 겨우 3% 높을 때
                    if curr_p < ma5 * 1.03:
                        conditions.append("❌ 5일선 이탈징후")
                        
                    # 2. 볼린저밴드: 상단선보다 7% 낮은 곳까지 허용
                    if curr_p > bb['BBU_20_2.0'].iloc[-1] * 0.93:
                        conditions.append("❌ 볼린저 상단 영역")
                        
                    # 3. MACD: 데드크로스 혹은 MACD선이 시그널선보다 아래에 있으면 허용
                    if macd_df['MACD_12_26_9'].iloc[-1] < macd_df['MACDs_12_26_9'].iloc[-1]:
                        conditions.append("❌ MACD 우하향")

                    if conditions:
                        diff = ((curr_p - prev_p) / prev_p) * 100
                        send_alert(f"🔴 [매도포착] {name}\n가: {curr_p:,} (+{diff:.2f}%)\nRSI: {rsi:.1f}\n" + "\n".join(conditions))
            except: continue
    except: pass
