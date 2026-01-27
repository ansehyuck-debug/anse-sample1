# Last updated: 2026-01-26 - Forced re-push for workflow debugging. Another re-push attempt.
import os
import json
import pandas as pd
import FinanceDataReader as fdr # 지표 1, 2에 필요
from pykrx import stock # pykrx는 더 이상 사용하지 않지만 FinanceDataReader가 의존할 수 있으므로 남겨둠
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
    # API에 따라 svc/apis/idx/ 또는 svc/apis/sto/ 등을 사용
    base_url = "https://data-dbg.krx.co.kr/svc/apis/"
    full_url = base_url + endpoint
    print(f"KRX API 호출: URL={full_url}, Params={params}") # Added logging
    try:
        response = requests.get(full_url, headers=headers, params=params, timeout=30) # Increased timeout
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
    endpoint = "idx/drvprod_dd_trd" # 파생상품지수 시세정보
    params = {"basDd": date_str}
    
    data = _call_krx_api(endpoint, params)
    
    vkospi_value = None
    if "OutBlock_1" in data:
        for item in data["OutBlock_1"]:
            # VKOSPI의 지수명을 정확히 확인해야 함. "VKOSPI" 또는 "코스피200 변동성지수" 등이 될 수 있음.
            # 일단 "VKOSPI"로 가정하고, 없으면 로그로 모든 지수명 출력하여 디버깅.
            if item.get("IDX_NM") == "코스피 200 변동성지수": 
                vkospi_value = float(item.get("CLSPRC_IDX").replace('-', '')) # '-' 제거 후 float 변환
                break
        if vkospi_value is None:
            all_idx_names = [item.get("IDX_NM") for item in data["OutBlock_1"]]
            print("KRX API에서 VKOSPI를 찾지 못했습니다. 확인된 지수명: %s" % str(all_idx_names))
            raise ValueError("VKOSPI 데이터를 찾을 수 없습니다 (IDX_NM not 'VKOSPI').")
    else:
        raise ValueError("KRX API 응답에 OutBlock_1이 없습니다.")
        
    return vkospi_value 

def get_adr_from_krx_api(date_str):
    endpoint = "sto/stk_bydd_trd" # 유가증권 일별매매정보
    params = {"basDd": date_str}

    data = _call_krx_api(endpoint, params)

    if "OutBlock_1" not in data or not data["OutBlock_1"]:
        raise ValueError("KRX API 응답에 OutBlock_1이 없거나 비어있습니다.")
    
    advancing_count = 0
    declining_count = 0
    
    for item in data["OutBlock_1"]:
        if item.get("MKT_NM") == "KOSPI": # KOSPI 시장만 필터링
            fluc_rt = float(item.get("FLUC_RT").replace('-', '0')) # 등락률, '-'인 경우 0으로 처리
            if fluc_rt > 0:
                advancing_count += 1
            elif fluc_rt < 0:
                declining_count += 1
    
    if declining_count == 0:
        adr_score_raw = 100 if advancing_count > 0 else 50 # 하락 종목이 없으면 상승 종목에 따라 점수
    else:
        adr_score_raw = (advancing_count / declining_count) * 100
    
    return adr_score_raw

def get_put_call_ratio_from_krx_api(date_str):
    endpoint = "drv/opt_bydd_trd" # 옵션 일별매매정보 (주식옵션外)
    params = {"basDd": date_str}

    data = _call_krx_api(endpoint, params)
    print(f"지표 5 (풋콜 비율) KRX API raw response for {date_str}: {json.dumps(data, indent=2)}") # Added logging

    if "OutBlock_1" not in data or not data["OutBlock_1"]:
        print(f"지표 5 (풋콜 비율) OutBlock_1 없음 또는 비어있음 for {date_str}. Response keys: {data.keys()}") # Added logging
        raise ValueError("KRX API 응답에 OutBlock_1이 없거나 비어있습니다.")
    
    put_volume = 0
    call_volume = 0
    
    # KOSPI 200 옵션 상품만 필터링하여 Put/Call 거래량 합산
    relevant_products = ["코스피200 옵션", "KOSPI200 옵션"] # Add other relevant names if found in logs
    filtered_items = []
    for item in data["OutBlock_1"]:
        prod_nm = item.get("PROD_NM", "")
        if any(prod_name in prod_nm for prod_name in relevant_products):
            filtered_items.append(item)
            
    print(f"지표 5 (풋콜 비율) 필터링된 OutBlock_1 내용 for {date_str}: {json.dumps(filtered_items, indent=2)}") # Added logging for filtered items

    if not filtered_items:
        print(f"지표 5 (풋콜 비율) 필터링된 KOSPI200 옵션 데이터 없음 for {date_str}. OutBlock_1은 있었으나 관련 상품 없음.")
        raise ValueError("필터링된 KOSPI200 옵션 데이터가 없습니다.")

    for item in filtered_items: # Iterate through filtered items
        try:
            acc_trdvol = float(item.get("ACC_TRDVOL").replace('-', '0'))
            if item.get("RGHT_TP_NM") == "PUT":
                put_volume += acc_trdvol
            elif item.get("RGHT_TP_NM") == "CALL":
                call_volume += acc_trdvol
        except ValueError as ve:
            print("거래량 변환 오류: %s (item: %s)" % (str(ve), str(item)))
            continue

    if put_volume == 0 and call_volume == 0:
        print(f"지표 5 (풋콜 비율) 필터링된 KOSPI200 옵션의 Put/Call 거래량 모두 0 for {date_str}. 중립(50)으로 처리합니다.")
        put_call_ratio = 50
    elif call_volume == 0:
        print(f"지표 5 (풋콜 비율) 필터링된 KOSPI200 옵션의 Call 거래량 0, Put 거래량 있음. Put/Call 비율 100으로 처리 for {date_str}.")
        put_call_ratio = 100 # Put volume exists, Call volume is zero
    else:
        put_call_ratio = (put_volume / call_volume) * 100
    
    return put_call_ratio

def get_scores():
    scores = []
    
    # 지표 1: KOSPI vs 125일 이평선 이격도
    try:
        df = fdr.DataReader('KS11', start=datetime.now() - timedelta(days=200))
        ma125 = df['Close'].rolling(window=125).mean().iloc[-1]
        curr = df['Close'].iloc[-1]
        score1 = min(max((curr/ma125 - 0.9) / 0.2 * 100, 0), 100)
        scores.append(score1)
        print("지표 1 (KOSPI vs 125일 이평선 이격도) 성공: %.2f" % score1)
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

    # 지표 3: ADR (상승/하락 비율) - KRX API 사용
    try:
        adr_score_raw = None
        for i in range(5): # 지난 5일간 데이터를 시도
            target_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
            try:
                adr_score_raw = get_adr_from_krx_api(target_date)
                if adr_score_raw is not None:
                    print("지표 3 (ADR): %s 데이터 사용." % target_date)
                    break
            except Exception as e_inner:
                print("지표 3 (ADR): %s 데이터 조회 실패. 재시도. 오류: %s" % (target_date, str(e_inner)))
                time.sleep(1) # 짧은 지연
        
        if adr_score_raw is None:
            raise ValueError("ADR 데이터를 5일 동안 찾지 못했습니다.")

        # ADR 값을 0~100 스케일로 변환. 일반적으로 70~120 범위. 100이 중립.
        if adr_score_raw <= 70:
            adr_score_scaled = 0
        elif adr_score_raw >= 120:
            adr_score_scaled = 100
        else:
            adr_score_scaled = (adr_score_raw - 70) / (120 - 70) * 100
        
        scores.append(adr_score_scaled)
        print("지표 3 (ADR) 성공: %.2f (원시값), %.2f (스케일된 값)" % (adr_score_raw, adr_score_scaled))
    except Exception as e:
        print("지표 3 (ADR) 최종 오류: %s" % str(e))
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
    
    # 지표 5: 풋콜 비율 - KRX API 사용
    try:
        put_call_ratio_raw = None
        for i in range(5): # 지난 5일간 데이터를 시도
            target_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
            try:
                put_call_ratio_raw = get_put_call_ratio_from_krx_api(target_date)
                if put_call_ratio_raw is not None:
                    print("지표 5 (풋콜 비율): %s 데이터 사용." % target_date)
                    break
            except Exception as e_inner:
                print("지표 5 (풋콜 비율): %s 데이터 조회 실패. 재시도. 오류: %s" % (target_date, str(e_inner)))
                time.sleep(1) # 짧은 지연
        
        if put_call_ratio_raw is None:
            raise ValueError("풋콜 비율 데이터를 5일 동안 찾지 못했습니다.")

        # 풋콜 비율을 0~100 스케일로 변환 (현재 raw 값은 백분율)
        # 일반적으로 풋콜 비율 (백분율)은 50~150 범위. 100이 중립.
        # 50 이하: 탐욕(100점), 150 이상: 공포(0점)
        if put_call_ratio_raw <= 50:
            put_call_score = 100
        elif put_call_ratio_raw >= 150:
            put_call_score = 0
        else:
            # put_call_ratio_raw가 50에서 150 사이일 때 선형 스케일링
            # 50 -> 100점, 150 -> 0점
            put_call_score = 100 - (put_call_ratio_raw - 50) / (150 - 50) * 100 # 선형 스케일링
        
        scores.append(put_call_score)
        print("지표 5 (풋콜 비율) 성공: %.2f (원시값), %.2f (스케일된 값)" % (put_call_ratio_raw, put_call_score))
    except Exception as e:
        print("지표 5 (풋콜 비율) 오류: %s" % str(e))
        scores.append(50)
    
    # 5개 지표의 평균 계산 (지표 수가 변경되었으므로 동적으로 계산)
    final_score = sum(scores) / len(scores) if scores else 50

    # KOSPI 현재 값, 등락률, 등락포인트 추가 (FinanceDataReader 재사용)
    kospi_value = None
    kospi_change_rate = None
    kospi_change_point = None
    try:
        df_kospi = fdr.DataReader('KS11', start=datetime.now() - timedelta(days=5)) # Get last few days for change calculation
        if not df_kospi.empty:
            curr_close = df_kospi['Close'].iloc[-1]
            prev_close = df_kospi['Close'].iloc[-2] # Previous day's close
            
            kospi_value = round(curr_close, 2)
            kospi_change_point = round(curr_close - prev_close, 2)
            kospi_change_rate = round((kospi_change_point / prev_close) * 100, 2)
            print(f"KOSPI 현재가: {kospi_value}, 등락포인트: {kospi_change_point}, 등락률: {kospi_change_rate}%")
        else:
            print("KOSPI 데이터를 FinanceDataReader에서 가져오지 못했습니다.")
    except Exception as e:
        print(f"KOSPI 데이터 가져오기 오류: {e}")

    return int(final_score), scores, kospi_value, kospi_change_point, kospi_change_rate

def get_status(score):
    phase = ""
    description = ""
    if score <= 25: 
        phase = "극심한 공포"
        description = "무섭게 떨어지네요.\n모두가 도망칠 때, 오히려 기회가 숨어 있다는데?!"
    elif score <= 45: 
        phase = "공포"
        description = "점점 무서워집니다.\n그래도 이런 구간에서는 그동안 사고 싶었던 주식을 잘 살펴봐요."
    elif score <= 55: 
        phase = "중립"
        description = "팔까, 살까… 헷갈리는 시기.\n타이밍을 재지 말고, 꾸준히 살 수 있는 주식을 잘 살펴봐요."
    elif score <= 75: 
        phase = "탐욕"
        description = "사람들의 욕심이 조금씩 느껴지네요.\n수익이 났다면, 신중한 매수가 필요한 때입니다. \n현금도 종목이다."
    else: 
        phase = "극심한 탐욕"
        description = "주린이도 주식 이야기뿐인 시장.\n나는 이제… 아무것도 안살란다. 떠나보낼 주식이라면 지금이 기회."
    return {"phase": phase, "description": description}


# 실행 및 Firestore 저장
score, individual_scores, kospi_value, kospi_change_point, kospi_change_rate = get_scores()
status_obj = get_status(score) # Changed to status_obj

# 중괄호를 피하기 위해 dict() 생성자 사용
data_to_save = dict(
    score=score,
    status=status_obj, # Save the object
    timestamp=firestore.SERVER_TIMESTAMP,
    kospi_value=kospi_value,
    kospi_change_point=kospi_change_point,
    kospi_change_rate=kospi_change_rate
)

for i, s in enumerate(individual_scores):
    # f-string 대신 문자열 결합 사용
    key_name = "indicator" + str(i + 1)
    data_to_save[key_name] = s

print("저장 완료: %d점 (%s)" % (score, status_obj["phase"])) # Print phase
formatted_scores = [format(s, ".2f") for s in individual_scores]
print("개별 지표: %s" % formatted_scores)

db.collection('korea_index').add(data_to_save)
