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

    # 지표 3: ADR (상승/하락 비율) - 웹 스크래핑 사용 (www.adrinfo.kr)
    try:
        url_adr = "http://www.adrinfo.kr/main/sub_adr_index.html"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url_adr, headers=headers)
        response.raise_for_status() # HTTP 오류 발생 시 예외 발생
        soup = BeautifulSoup(response.text, 'html.parser')
        
        adr_value_tag = soup.select_one('td.tbl_adr')
        if adr_value_tag:
            adr_text = adr_value_tag.get_text(strip=True)
            adr_score = float(adr_text)
            adr_score_scaled = min(max((adr_score - 50) / 100 * 100, 0), 100) # 예시 스케일링
            scores.append(adr_score_scaled)
            print(f"지표 3 (ADR) 성공: {adr_score:.2f} (원시값), {adr_score_scaled:.2f} (스케일된 값)")
        else:
            raise ValueError("ADR 웹사이트에서 값을 찾을 수 없습니다.")

    except Exception as e:
        print(f"지표 3 (ADR) 오류: {e}")
        scores.append(50)

    # 지표 4: VKOSPI (변동성) - 웹 스크래핑 사용 (Investing.com)
    try:
        url_vkospi = "https://kr.investing.com/indices/kospi-volatility"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url_vkospi, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Investing.com 페이지에서 VKOSPI 값을 찾기
        # 이 셀렉터는 웹사이트의 현재 구조를 기반으로 추정됨.
        # 개발자 도구로 실제 페이지의 요소를 확인하여 정확한 셀렉터를 찾아야 함.
        # 일반적으로 실시간 가격은 'last_last' 같은 ID를 가진 span/div에 있음.
        vkospi_value_tag = soup.select_one('div.text-5xl > span#last_last') # 현재 가격을 나타내는 셀렉터 추정
        if not vkospi_value_tag:
            # 다른 셀렉터 시도 (예: 이전 버전 또는 다른 구조)
            vkospi_value_tag = soup.select_one('span.instrument-price_last__FXKj4')

        if vkospi_value_tag:
            vkospi_text = vkospi_value_tag.get_text(strip=True).replace(',', '') # 콤마 제거
            vix = float(vkospi_text)
            v_score = 100 - (min(max((vix - 17) / 20 * 100, 0), 100))
            scores.append(v_score)
            print(f"지표 4 (VKOSPI) 성공: {vix:.2f} (원시값), {v_score:.2f} (스케일된 값)")
        else:
            raise ValueError("Investing.com 페이지에서 VKOSPI 값을 찾을 수 없습니다.")

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
