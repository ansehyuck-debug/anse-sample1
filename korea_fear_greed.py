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

    # 지표 3: ADR (상승/하락 비율) - FinanceDataReader 사용 (ChgRatio 수정)
    try:
        df_kospi_listing = fdr.StockListing('KOSPI')
        # 상승 종목 수: ChangeRatio 대신 ChgRatio 사용
        ups = len(df_kospi_listing[df_kospi_listing['ChgRatio'] > 0])
        # 하락 종목 수: ChangeRatio 대신 ChgRatio 사용
        downs = len(df_kospi_listing[df_kospi_listing['ChgRatio'] < 0])

        adr_score = (ups / (ups + downs + 1)) * 100 if (ups + downs) > 0 else 50
        # ADR 값은 0~200 사이로 나오므로, 100을 중립으로 보고 스케일링
        adr_score_scaled = min(max((adr_score - 50) / 100 * 100, 0), 100)
        
        scores.append(adr_score_scaled)
        print(f"지표 3 (ADR) 성공: {adr_score:.2f} (원시값), {adr_score_scaled:.2f} (스케일된 값)")
    except Exception as e:
        print(f"지표 3 (ADR) 오류: {e}")
        scores.append(50)

    # 지표 4: VKOSPI (변동성) - FinanceDataReader KSVIX 심볼 사용 및 Investing.com 폴백
    try:
        vkospi_df = fdr.DataReader('KSVIX', start=datetime.now() - timedelta(days=30))
        vix = vkospi_df['Close'].iloc[-1]
        
        window_size = min(len(vkospi_df), 20)
        if window_size > 0:
            low = vkospi_df['Close'].rolling(window=window_size).min().iloc[-1]
            high = vkospi_df['Close'].rolling(window=window_size).max().iloc[-1]
            if high - low == 0:
                v_score = 50
            else:
                v_score = 100 * (1 - (vix - low) / (high - low))
        else:
            v_score = 50

        scores.append(v_score)
        print(f"지표 4 (VKOSPI) 성공: {vix:.2f} (원시값), {v_score:.2f} (스케일된 값)")
    except Exception as e_ksvix:
        print(f"지표 4 (VKOSPI) KSVIX 오류: {e_ksvix}. Investing.com 폴백 시도.")
        try:
            # Investing.com 소스 사용 (fdr.DataReader의 동작 확인 필요)
            df_vix_investing = fdr.DataReader('V-KOSPI 200', data_source='investing', start=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
            vix_investing = df_vix_investing['Close'].iloc[-1]
            
            window_size_inv = min(len(df_vix_investing), 20)
            if window_size_inv > 0:
                low_inv = df_vix_investing['Close'].rolling(window=window_size_inv).min().iloc[-1]
                high_inv = df_vix_investing['Close'].rolling(window=window_size_inv).max().iloc[-1]
                if high_inv - low_inv == 0:
                    v_score_inv = 50
                else:
                    v_score_inv = 100 * (1 - (vix_investing - low_inv) / (high_inv - low_inv))
            else:
                v_score_inv = 50

            scores.append(v_score_inv)
            print(f"지표 4 (VKOSPI) Investing.com 성공: {vix_investing:.2f} (원시값), {v_score_inv:.2f} (스케일된 값)")
        except Exception as e_investing:
            print(f"지표 4 (VKOSPI) Investing.com 폴백 오류: {e_investing}")
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
