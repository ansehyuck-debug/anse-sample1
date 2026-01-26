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
    
    # 휴장일 처리를 위해 가장 최근의 영업일 조회
    today_str = datetime.now().strftime("%Y%m%d")
    recent_bday = stock.get_nearest_business_day_in_a_week(date=today_str)
    
    # 지표 1: KOSPI vs 125일 이평선 이격도
    try:
        df = fdr.DataReader('KS11')
        ma125 = df['Close'].rolling(window=125).mean().iloc[-1]
        curr = df['Close'].iloc[-1]
        score1 = min(max((curr/ma125 - 0.9) / 0.2 * 100, 0), 100)
        scores.append(score1)
    except:
        scores.append(50)

    # 지표 2: 신고가/신저가 비율 (최근 영업일 기준)
    try:
        high = len(stock.get_market_number_of_250days_high_low(recent_bday, "KOSPI")['신고가'])
        low = len(stock.get_market_number_of_250days_high_low(recent_bday, "KOSPI")['신저가'])
        score2 = (high / (high + low + 1)) * 100
        scores.append(score2)
    except:
        scores.append(50)

    # 지표 3: ADR (상승/하락 비율) - 실제 계산 버전 (최근 영업일 기준)
    try:
        df_adr = stock.get_market_price_change_by_ticker(recent_bday, recent_bday, "KOSPI")
        ups = (df_adr['종가'] > df_adr['시가']).sum()
        downs = (df_adr['종가'] < df_adr['시가']).sum()
        adr_score = (ups / (ups + downs + 1)) * 100
        scores.append(adr_score)
    except:
        scores.append(50) # 에러 시 중립값

    # 지표 4: VKOSPI (변동성) - fdr이 마지막 거래일 데이터를 자동으로 가져오므로 날짜 지정 불필요
    try:
        vix = fdr.DataReader('KSVIX').iloc[-1]['Close']
        v_score = 100 - (min(max((vix - 15) / 20 * 100, 0), 100))
        scores.append(v_score)
    except:
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