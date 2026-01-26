import os
import json
import pandas as pd
import FinanceDataReader as fdr
from pykrx import stock
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore

# 1. Firebase 초기화
if not firebase_admin._apps:
    firebase_key = os.environ.get('FIREBASE_KEY')
    
    if firebase_key:
        key_dict = json.loads(firebase_key)
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
        print("GitHub Secrets 키를 사용하여 인증되었습니다.")
    else:
        cred = credentials.ApplicationDefault() 
        firebase_admin.initialize_app(cred)
        print("기존 ApplicationDefault 방식을 사용하여 인증되었습니다.")

db = firestore.client()

def get_scores():
    scores = []
    
    # 지표 1: KOSPI vs 125일 이평선 이격도
    try:
        df = fdr.DataReader('KS11', start=datetime.now() - timedelta(days=200))
        ma125 = df['Close'].rolling(window=125).mean().iloc[-1]
        curr = df['Close'].iloc[-1]
        score1 = min(max((curr/ma125 - 0.9) / 0.2 * 100, 0), 100)
        scores.append(score1)
    except Exception as e:
        print(f"지표 1 오류: {e}")
        scores.append(50)

    # 지표 2: KOSPI 14일 RSI (대체 지표)
    try:
        df_rsi = fdr.DataReader('KS11', start=datetime.now() - timedelta(days=40))
        delta = df_rsi['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_score = rsi.iloc[-1]
        scores.append(rsi_score)
        print(f"지표 2 (RSI) 성공: {rsi_score:.2f}")
    except Exception as e:
        print(f"지표 2 (RSI) 오류: {e}")
        scores.append(50)

    # 지표 3: ADR (상승/하락 비율) - FinanceDataReader 사용
    try:
        # 오늘 날짜를 기준으로 코스피 전 종목의 등락률 가져오기
        today_date = datetime.now().strftime('%Y%m%d')
        # pykrx의 get_market_price_change_by_ticker는 해당 날짜의 등락 정보 제공
        # fdr.StockListing은 현재 시점의 등락률이기에 과거 데이터와의 일관성을 위해 pykrx 사용
        # 단, pykrx가 안정적이지 않으므로, 5일간 반복 로직은 유지하되, pykrx 대신 fdr.StockListing을 활용
        
        # NOTE: fdr.StockListing()은 실시간 데이터에 가깝고, 과거 특정일의 등락 종목 수를 제공하지 않음.
        # ADR 계산은 일반적으로 과거 일정 기간(예: 20일)의 상승/하락 종목 수 누적값을 사용함.
        # pykrx의 get_market_price_change_by_ticker가 지속적으로 실패하는 문제가 있으므로,
        # ADR 지표를 FinanceDataReader를 이용해 계산할 수 있는 다른 방식으로 대체하거나,
        # ADR 지표 자체를 단순화해야 함.
        # 일단은 사용자 제안처럼 '오늘'의 상승/하락 종목수를 기반으로 ADR을 계산.
        # 이 방법은 ADR 지표의 본래 의미와 다소 차이가 있을 수 있음.

        df_kospi_listing = fdr.StockListing('KOSPI')
        # 상승 종목 수: ChangeRate가 0보다 큰 종목 (즉, 상승)
        ups = len(df_kospi_listing[df_kospi_listing['ChangeRatio'] > 0])
        # 하락 종목 수: ChangeRate가 0보다 작은 종목 (즉, 하락)
        downs = len(df_kospi_listing[df_kospi_listing['ChangeRatio'] < 0])

        adr_score = (ups / (ups + downs + 1)) * 100 if (ups + downs) > 0 else 50
        # ADR 값은 0~200 사이로 나오므로, 100을 중립으로 보고 스케일링
        adr_score_scaled = min(max((adr_score - 50) / 100 * 100, 0), 100)
        
        scores.append(adr_score_scaled)
        print(f"지표 3 (ADR) 성공: {adr_score:.2f} (원시값), {adr_score_scaled:.2f} (스케일된 값)")
    except Exception as e:
        print(f"지표 3 (ADR) 오류: {e}")
        scores.append(50)

    # 지표 4: VKOSPI (변동성) - FinanceDataReader KSVIX 심볼 사용
    try:
        # FinanceDataReader의 KSVIX 심볼 사용
        vkospi_df = fdr.DataReader('KSVIX', start=datetime.now() - timedelta(days=30))
        vix = vkospi_df['Close'].iloc[-1]
        
        # 사용자 제안처럼 과거 252일 (약 1년) 동안의 최소/최대값 대비 현재 위치 계산
        # 다만, 30일치 데이터만 가져왔으므로 window를 20일 정도로 조정
        window_size = min(len(vkospi_df), 20) # 데이터가 20개 미만일 경우 데이터 길이에 맞춤

        if window_size > 0:
            low = vkospi_df['Close'].rolling(window=window_size).min().iloc[-1]
            high = vkospi_df['Close'].rolling(window=window_size).max().iloc[-1]
            if high - low == 0: # 분모가 0이 되는 경우 방지
                v_score = 50
            else:
                # 수치가 높을수록 공포이므로 반전 처리 (0~100으로 스케일링)
                v_score = 100 * (1 - (vix - low) / (high - low))
        else:
            v_score = 50 # 데이터가 부족할 경우 중립값

        scores.append(v_score)
        print(f"지표 4 (VKOSPI) 성공: {vix:.2f} (원시값), {v_score:.2f} (스케일된 값)")
    except Exception as e:
        print(f"지표 4 (VKOSPI) 오류: {e}")
        scores.append(50)
    
    # 4개 지표의 평균 계산
    final_score = sum(scores) / len(scores) if scores else 50
    return int(final_score), scores

def get_status(score):
    if score <= 25: return "극심한 공포 : 무섭게 떨어지네요.\n모두가 도망칠 때, 오히려 기회가 숨어 있다는데?!"
    elif score <= 45: return "공포 : 점점 무서워집니다.\n그래도 이런 구간에서는 그동안 사고 싶었던 주식을 잘 살펴봐요."
    elif score <= 55: return "중립 : 팔까, 살까… 헷갈리는 시기.\n타이밍을 재지 말고, 꾸준히 살 수 있는 주식을 잘 살펴봐요."
    elif score <= 75: return "탐욕 : 사람들의 욕심이 조금씩 느껴지네요.\n수익이 났다면, 신중한 매수가 필요한 때입니다. \n현금도 종목이다."
    else: return "극심한 탐욕 : 주린이도 주식 이야기뿐인 시장.\n나는 이제… 아무것도 안살란다. 떠나보낼 주식이라면 지금이 기회."

# 실행 및 Firestore 저장
score, individual_scores = get_scores()
status = get_status(score)

data_to_save = {
    'score': score,
    'status': status,
    'timestamp': firestore.SERVER_TIMESTAMP
}
for i, s in enumerate(individual_scores):
    data_to_save[f'indicator{i+1}'] = s

db.collection('korea_index').add(data_to_save)

print(f"저장 완료: {score}점 ({status})")
print(f"개별 지표: {[f'{s:.2f}' for s in individual_scores]}")