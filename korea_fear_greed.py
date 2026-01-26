# Last updated: 2026-01-26 - Forced re-push for workflow debugging. Another re-push attempt.
import os
import json
import pandas as pd
import FinanceDataReader as fdr # 지표 1, 2에 필요
from pykrx import stock
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
import time # 재시도를 위한 시간 지연

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

def _call_krx_api(endpoint, params, auth_key_env_var="KRX_API_KEY"):
    auth_key = os.environ.get(auth_key_env_var)
    if not auth_key:
        raise ValueError("환경 변수 '%s'가 KRX API 키로 설정되지 않았습니다." % auth_key_env_var)
    
    headers = {
        "AUTH_KEY": auth_key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    # KRX Open API의 기본 URL이 data-dbg.krx.co.kr 이므로 이를 사용
    url = "https://data-dbg.krx.co.kr/svc/apis/idx/" + endpoint # 파생상품지수 시세정보는 idx 엔드포인트 사용

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status() # HTTP 오류 발생 시 예외 발생
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print("HTTP 오류 발생: %s" % http_err)
        print("응답 내용: %s" % response.text)
        raise
    except requests.exceptions.ConnectionError as conn_err:
        print("연결 오류 발생: %s" % conn_err)
        raise
    except requests.exceptions.Timeout as timeout_err:
        print("요청 시간 초과: %s" % timeout_err)
        raise
    except requests.exceptions.RequestException as req_err:
        print("요청 오류 발생: %s" % req_err)
        raise

def get_vkospi_from_krx_api(date_str):
    endpoint = "drvprod_dd_trd" # 파생상품지수 시세정보
    params = {"basDd": date_str}
    
    data = _call_krx_api(endpoint, params)
    
    vkospi_value = None
    if "OutBlock_1" in data:
        for item in data["OutBlock_1"]:
            # VKOSPI의 지수명을 정확히 확인해야 함. "VKOSPI" 또는 "코스피200 변동성지수" 등이 될 수 있음.
            # 일단 "VKOSPI"로 가정하고, 없으면 로그로 모든 지수명 출력하여 디버깅.
            if item.get("IDX_NM") == "VKOSPI": 
                vkospi_value = float(item.get("CLSPRC_IDX").replace('-', '')) # '-' 제거 후 float 변환
                break
        if vkospi_value is None:
            all_idx_names = [item.get("IDX_NM") for item in data["OutBlock_1"]]
            print("KRX API에서 VKOSPI를 찾지 못했습니다. 확인된 지수명: %s" % str(all_idx_names))
            raise ValueError("VKOSPI 데이터를 찾을 수 없습니다 (IDX_NM not 'VKOSPI').")
    else:
        raise ValueError("KRX API 응답에 OutBlock_1이 없습니다.")
        
    return vkospi_value


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
        print("지표 1 오류: %s" % str(e))
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
        print("지표 2 (RSI) 성공: %.2f" % rsi_score)
    except Exception as e:
        print("지표 2 (RSI) 오류: %s" % str(e))
        scores.append(50)

    # 지표 3: ADR (상승/하락 비율) - pykrx 사용은 실패, KRX API 또는 다른 소스 필요
    # 현재는 오류가 나고 있으므로 임시로 50 처리
    print("지표 3 (ADR) 현재 KRX API 구현 대기 중이므로 50 처리.")
    scores.append(50)


    # 지표 4: VKOSPI (변동성) - KRX API 사용
    try:
        vkospi_value = None
        for i in range(5): # 지난 5일간 데이터를 시도
            target_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
            try:
                vkospi_value = get_vkospi_from_krx_api(target_date)
                if vkospi_value is not None:
                    print("지표 4 (VKOSPI): %s 데이터 사용." % target_date)
                    break
            except Exception as e_inner:
                print("지표 4 (VKOSPI): %s 데이터 조회 실패. 재시도. 오류: %s" % (target_date, str(e_inner)))
                time.sleep(1) # 짧은 지연

        if vkospi_value is None:
            raise ValueError("VKOSPI 데이터를 5일 동안 찾지 못했습니다.")

        vix = vkospi_value
        
        # 20일 윈도우 min/max 기반 스케일링
        # KRX API는 일별 데이터만 제공하므로, 20일치 데이터를 얻으려면 여러 번 호출 필요
        # 아니면 한 번에 긴 기간을 요청하는 API를 찾아야 함.
        # 일단은 현재 가져온 1일치 VKOSPI 값으로 직접 스케일링
        # VKOSPI의 일반적인 범위는 10~40.
        # 10 이하: 극심한 탐욕 (100점), 40 이상: 극심한 공포 (0점)
        if vix <= 10:
            v_score = 100
        elif vix >= 40:
            v_score = 0
        else:
            v_score = 100 - (vix - 10) / (40 - 10) * 100 # 선형 스케일링
        
        scores.append(v_score)
        print("지표 4 (VKOSPI) 성공: %.2f (원시값), %.2f (스케일된 값)" % (vix, v_score))
    except Exception as e:
        print("지표 4 (VKOSPI) 오류: %s" % str(e))
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

# 중괄호를 피하기 위해 dict() 생성자 사용
data_to_save = dict(
    score=score,
    status=status,
    timestamp=firestore.SERVER_TIMESTAMP
)

for i, s in enumerate(individual_scores):
    # f-string 대신 문자열 결합 사용
    key_name = "indicator" + str(i + 1)
    data_to_save[key_name] = s

print("저장 완료: %d점 (%s)" % (score, status))
formatted_scores = [format(s, ".2f") for s in individual_scores]
print("개별 지표: %s" % formatted_scores)

db.collection('korea_index').add(data_to_save)