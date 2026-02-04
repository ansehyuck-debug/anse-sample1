# Last updated: 2026-01-26 - Forced re-push for workflow debugging. Another re-push attempt.
import os
import json
import pandas as pd
import FinanceDataReader as fdr # 지표 1, 2에 필요
from pykrx import stock # pykrx는 더 이상 사용하지 않지만 FinanceDataReader가 의존할 수 있으므로 남겨둠
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, datetime # Add datetime import for use in generate_gemini_report
import firebase_admin
from firebase_admin import credentials, firestore
import time # 재시도를 위한 시간 지연
# [수정] 기존 'import google.generativeai' 대신 최신 SDK 임포트
from google import genai 
from google.genai import types

# 1. Firebase 초기화
firestore_initialized = False
db = None
if not firebase_admin._apps:
    try:
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
        firestore_initialized = True
    except Exception as e:
        print(f"Firebase 초기화 중 오류 발생: {e}. Firestore에 데이터를 저장할 수 없습니다.")
else: # Already initialized, likely in a testing environment or subsequent call
    try:
        db = firestore.client()
        firestore_initialized = True
    except Exception as e:
        print(f"이미 초기화된 Firebase 앱에서 Firestore 클라이언트 가져오기 오류: {e}. Firestore에 데이터를 저장할 수 없습니다.")


def _call_krx_api(endpoint, params, auth_key_env_var="KRX_API_KEY"):
    auth_key = os.environ.get(auth_key_env_var)
    if not auth_key:
        print(f"경고: 환경 변수 '{auth_key_env_var}'가 KRX API 키로 설정되지 않았습니다. KRX API 호출을 건너뜝니다.")
        return None
    
    headers = {
        "AUTH_KEY": auth_key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    # KRX Open API의 기본 URL이 data-dbg.krx.co.kr 이므로 이를 사용
    # API에 따라 svc/apis/idx/ 또는 svc/apis/sto/ 등을 사용
    base_url = "https://data-dbg.krx.co.kr/svc/apis/"
    full_url = base_url + endpoint
    # print(f"KRX API 호출: URL={full_url}, Params={params}") # Removed verbose logging
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

def get_adr_counts_from_krx_api(date_str):
    endpoint = "sto/stk_bydd_trd" # 유가증권 일별매매정보
    params = {"basDd": date_str}

    try:
        data = _call_krx_api(endpoint, params)
        if data is None or "OutBlock_1" not in data or not data["OutBlock_1"]:
            return None, None
        
        advancing_count = 0
        declining_count = 0
        
        for item in data["OutBlock_1"]:
            # KOSPI 시장의 '주권'(보통주/우선주)만 필터링하여 전통적 ADR 계산
            if item.get("MKT_NM") == "KOSPI":
                # SECT_TP_NM 필터링 (ETF, ETN 등 제외하고 주식만 집계)
                sect_tp = item.get("SECT_TP_NM")
                if sect_tp and sect_tp != "주권":
                    continue

                fluc_rt_str = item.get("FLUC_RT", "0")
                if fluc_rt_str == "-":
                    fluc_rt = 0.0
                else:
                    try:
                        fluc_rt = float(fluc_rt_str)
                    except ValueError:
                        fluc_rt = 0.0

                if fluc_rt > 0:
                    advancing_count += 1
                elif fluc_rt < 0:
                    declining_count += 1
        return advancing_count, declining_count
    except Exception as e:
        print(f"ADR 데이터 추출 중 오류 ({date_str}): {e}")
        return None, None

def get_put_call_ratio_from_krx_api(date_str):
    endpoint = "drv/opt_bydd_trd" # 옵션 일별매매정보 (주식옵션外)
    params = {"basDd": date_str}

    data = _call_krx_api(endpoint, params)
    
    # _call_krx_api에서 None을 반환한 경우 (예: KRX_API_KEY 없음)
    if data is None:
        # print(f"지표 5 (코스피200 옵션 풋콜 비율) KRX API 호출 실패로 None 반환 for {date_str}.") # Keep critical warnings
        return None

    # print(f"지표 5 (코스피200 옵션 풋콜 비율) KRX API raw response for {date_str} (from drv/opt_bydd_trd): {json.dumps(data, indent=2)}") # Removed verbose logging

    if "OutBlock_1" not in data or not data["OutBlock_1"]:
        # print(f"지표 5 (코스피200 옵션 풋콜 비율) OutBlock_1 없음 또는 비어있음 for {date_str}. Response keys: {data.keys()}. None을 반환합니다.") # Keep critical warnings
        return None
    
    put_volume = 0
    call_volume = 0
    
    # '코스피200 옵션' 상품만 필터링
    target_prod_nm = "코스피200 옵션"
    filtered_items = []
    
    # all_prod_names_in_block = [item.get("PROD_NM", "") for item in data["OutBlock_1"]]
    # print(f"지표 5 (코스피200 옵션 풋콜 비율) OutBlock_1 모든 PROD_NM for {date_str} (drv/opt_bydd_trd): {all_prod_names_in_block}") # Removed verbose logging

    for item in data["OutBlock_1"]:
        prod_nm = item.get("PROD_NM", "")
        if prod_nm == target_prod_nm:
            filtered_items.append(item)
            
    # print(f"지표 5 (코스피200 옵션 풋콜 비율) 필터링된 OutBlock_1 내용 for {date_str}: {json.dumps(filtered_items, indent=2)}") # Removed verbose logging

    if not filtered_items:
        # print(f"지표 5 (코스피200 옵션 풋콜 비율) '{target_prod_nm}' 데이터 없음 for {date_str}. OutBlock_1은 있었으나 관련 상품 없음. None을 반환합니다.") # Keep critical warnings
        return None

    for item in filtered_items:
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
        # print(f"지표 5 (코스피200 옵션 풋콜 비율) Put/Call 거래량 모두 0 for {date_str}. None을 반환합니다.") # Keep critical warnings
        return None # Return None if no volume to signify no meaningful data
    elif call_volume == 0:
        # print(f"지표 5 (코스피200 옵션 풋콜 비율) Call 거래량 0, Put 거래량 있음. Put/Call 비율 200으로 처리 for {date_str}.") # Keep critical warnings
        put_call_ratio = 200 # Put volume exists, Call volume is zero (extreme fear)
    else:
        put_call_ratio = (put_volume / call_volume) * 100
    
    return put_call_ratio

def get_scores():
    scores = []
    
    # 지표 1: KOSPI vs 125일 이평선 이격도
    try:
        score1 = 50 # 기본값 설정
        for i in range(10): # 오늘부터 10일 전까지 시도
            target_date = datetime.now() - timedelta(days=i)
            try:
                df = fdr.DataReader('KS11', start=target_date - timedelta(days=200))
                if not df.empty and len(df) >= 125: # 최소 125일 데이터 필요
                    ma125 = df['Close'].rolling(window=125).mean().iloc[-1]
                    curr = df['Close'].iloc[-1]
                    score1 = min(max((curr/ma125 - 0.9) / 0.2 * 100, 0), 100)
                    print(f"지표 1 (KOSPI vs 125일 이평선 이격도) 성공: {target_date.strftime('%Y%m%d')} 데이터 사용, 점수: {score1:.2f}")
                    break
                else:
                    print(f"지표 1 (KOSPI vs 125일 이평선 이격도): {target_date.strftime('%Y%m%d')} 데이터 부족. 재시도.")
            except Exception as e_inner:
                print(f"지표 1 (KOSPI vs 125일 이평선 이격도): {target_date.strftime('%Y%m%d')} 데이터 조회 실패. 재시도. 오류: {e_inner}")
            time.sleep(0.5) # 짧은 지연
        scores.append(score1)
        if score1 == 50: # 여전히 기본값이면 10일 동안 데이터를 찾지 못한 것
             print("지표 1 (KOSPI vs 125일 이평선 이격도) 최종 오류: 10일 동안 유효한 데이터를 찾지 못했습니다. 기본값 50 사용.")
    except Exception as e:
        print("지표 1 (KOSPI vs 125일 이평선 이격도) 최종 오류: %s" % str(e))
        scores.append(50)

    # 지표 2: KOSPI 14일 RSI (대체 지표)
    try:
        rsi_score = 50 # 기본값 설정
        for i in range(10): # 오늘부터 10일 전까지 시도
            target_date = datetime.now() - timedelta(days=i)
            try:
                # RSI 계산을 위해 넉넉한 기간의 데이터 필요 (14일 + 1일 diff)
                df_rsi = fdr.DataReader('KS11', start=target_date - timedelta(days=40)) 
                if not df_rsi.empty and len(df_rsi) > 14: # 최소 14일 데이터 필요
                    delta = df_rsi['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                    rsi_score = rsi.iloc[-1]
                    print(f"지표 2 (RSI) 성공: {target_date.strftime('%Y%m%d')} 데이터 사용, 점수: {rsi_score:.2f}")
                    break
                else:
                    print(f"지표 2 (RSI): {target_date.strftime('%Y%m%d')} 데이터 부족. 재시도.")
            except Exception as e_inner:
                print(f"지표 2 (RSI): {target_date.strftime('%Y%m%d')} 데이터 조회 실패. 재시도. 오류: {e_inner}")
            time.sleep(0.5) # 짧은 지연
        scores.append(rsi_score)
        if rsi_score == 50: # 여전히 기본값이면 10일 동안 데이터를 찾지 못한 것
             print("지표 2 (RSI) 최종 오류: 10일 동안 유효한 데이터를 찾지 못했습니다. 기본값 50 사용.")
    except Exception as e:
        print("지표 2 (RSI) 최종 오류: %s" % str(e))
        scores.append(50)

    # 지표 3: ADR (상승/하락 비율) - 20일 이동평균 (신뢰성 강화 버전)
    try:
        # 최근 45일치 데이터를 가져와서 충분한 거래일 후보 확보
        df_ks = fdr.DataReader('KS11', start=datetime.now() - timedelta(days=45))
        all_trading_days = df_ks.index.strftime('%Y%m%d').tolist()
        all_trading_days.reverse() # 최신 날짜부터 역순으로 검사
        
        total_adv = 0
        total_dec = 0
        days_found = 0
        
        print(f"지표 3 (ADR): 유효 20거래일 데이터 보장 수집 시작 (후보군 {len(all_trading_days)}일)...")
        for t_date in all_trading_days:
            adv, dec = get_adr_counts_from_krx_api(t_date)
            
            # 데이터가 존재하고 하락 종목이 0보다 큰 정상적인 데이터만 합산
            if adv is not None and dec is not None and dec > 0:
                total_adv += adv
                total_dec += dec
                days_found += 1
            
            # 정확히 20일치가 모이면 중단
            if days_found == 20:
                break
            time.sleep(0.1) # API 부하 방지
        
        if days_found == 20 and total_dec > 0:
            adr_score_raw = (total_adv / total_dec) * 100
            
            # ADR 값을 0~100 스케일로 변환 (70~120 범위 사용)
            if adr_score_raw <= 70:
                adr_score_scaled = 0
            elif adr_score_raw >= 120:
                adr_score_scaled = 100
            else:
                adr_score_scaled = (adr_score_raw - 70) / (120 - 70) * 100
            
            scores.append(adr_score_scaled)
            print("지표 3 (ADR) 성공: %.2f (원시값), %.2f (스케일된 값) [정확히 %d일 데이터 합산]" % (adr_score_raw, adr_score_scaled, days_found))
        else:
            print("지표 3 (ADR) 최종 오류: 유효한 20거래일 데이터를 확보하지 못했습니다. (확보된 일수: %d일) 기본값 50 사용." % days_found)
            scores.append(50)
    except Exception as e:
        print("지표 3 (ADR) 최종 오류: %s" % str(e))
        scores.append(50)

    # 지표 4: VKOSPI (변동성) - KRX API 사용
    try:
        vkospi_value = None
        for i in range(10): # 지난 10일간 데이터를 시도
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
            print("지표 4 (VKOSPI) 최종 오류: 10일 동안 데이터를 찾지 못했습니다. 기본값 50 사용.")
            scores.append(50)
        else:
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
    
    # 지표 5: 코스피200 옵션 풋콜 비율 - KRX API 사용
    try:
        put_call_ratio_raw = None
        for i in range(10): # 지난 10일간 데이터를 시도
            target_date = datetime.now() - timedelta(days=i)
            target_date_str = target_date.strftime("%Y%m%d") # API 호출 및 프린트용 문자열 날짜
            try:
                temp_put_call_ratio_raw = get_put_call_ratio_from_krx_api(target_date_str)
                if temp_put_call_ratio_raw is not None: 
                    put_call_ratio_raw = temp_put_call_ratio_raw
                    print(f"지표 5 (코스피200 옵션 풋콜 비율): {target_date_str} 데이터 사용.")
                    break
            except Exception as e_inner:
                print(f"지표 5 (코스피200 옵션 풋콜 비율): {target_date_str} 데이터 조회 실패. 재시도. 오류: {e_inner}")
                time.sleep(1)
        
        if put_call_ratio_raw is None:
            print("지표 5 (코스피200 옵션 풋콜 비율) 최종 오류: 10일 동안 데이터를 찾지 못했습니다. 기본값 50 사용.")
            scores.append(50)
        else:
            # PCR이 100(1.0)을 기준으로 어떻게 변하는지 매핑
            # 보통 70(탐욕) ~ 130(공포) 범위를 많이 사용하지만, 조금 더 넓은 범위를 사용합니다.
            # 제안 (조금 더 넓은 범위): 60(탐욕) ~ 180(공포)
            if put_call_ratio_raw <= 60:
                put_call_score = 100
            elif put_call_ratio_raw >= 180:
                put_call_score = 0
            else:
                # 역비례 계산 (낮을수록 점수 높음)
                put_call_score = 100 - (put_call_ratio_raw - 60) / (180 - 60) * 100
            
            scores.append(put_call_score)
            print("지표 5 (코스피200 옵션 풋콜 비율) 성공: %.2f (원시값), %.2f (스케일된 값)" % (put_call_ratio_raw, put_call_score))
    except Exception as e:
        print("지표 5 (코스피200 옵션 풋콜 비율) 오류: %s" % str(e))
        scores.append(50)
    
    # final_score = sum(scores) / len(scores) if scores else 50
    # 가중치 적용: 지표 1: 25%, 지표 2,3,4: 20%, 지표 5: 15%
    if len(scores) == 5:
        final_score = (scores[0] * 0.25 + scores[1] * 0.20 + scores[2] * 0.20 + scores[3] * 0.20 + scores[4] * 0.15)
    else:
        # scores 리스트의 길이가 5가 아닌 경우 (예외 발생 시) 기본값 50을 사용하거나 다른 처리 로직 추가
        # 현재 코드에서는 각 지표 계산 실패 시 50을 append하므로 이 else 블록에 도달할 일은 거의 없음.
        print("경고: scores 리스트의 길이가 5가 아닙니다. 가중치 계산 대신 기본값 50을 사용합니다.")
        final_score = 50

    kospi_value = None
    kospi_change_rate = None
    kospi_change_point = None
    try:
        df_kospi = fdr.DataReader('KS11', start=datetime.now() - timedelta(days=5))
        if not df_kospi.empty:
            curr_close = df_kospi['Close'].iloc[-1]
            prev_close = df_kospi['Close'].iloc[-2]
            
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
    if score < 20: 
        phase = "극심한 공포"
        description = "무섭게 떨어지네요.\n모두가 도망칠 때, 오히려 기회가 숨어 있다는데?!"
    elif score < 40: 
        phase = "공포"
        description = "점점 무서워집니다.\n그래도 이런 구간에서는 그동안 사고 싶었던 주식을 잘 살펴봐요."
    elif score < 60: 
        phase = "중립"
        description = "팔까, 살까… 헷갈리는 시기.\n타이밍을 재지 말고, 꾸준히 살 수 있는 주식을 잘 살펴봐요."
    elif score < 80: 
        phase = "탐욕"
        description = "사람들의 욕심이 조금씩 느껴지네요.\n수익이 났다면, 신중한 매수가 필요한 때입니다. \n현금도 종목이다."
    else:
        phase = "극심한 탐욕"
        description = "주린이도 주식 이야기뿐인 시장.\n나는 이제… 아무것도 안살란다. 떠나보낼 주식이라면 지금이 기회."
    return {"phase": phase, "description": description}

# [추가] 제미나이 리포트 생성 함수 (이름/정책 변화에 무관한 자동화 버전)
# [교체할 부분] 제미나이 리포트 생성 함수
def generate_gemini_report(data):
    from google import genai 
    from google.genai import types
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("에러: GEMINI_API_KEY 환경변수가 없습니다.")
        return

    try:
        # 1. 클라이언트 설정 (사용자님이 찾으신 문서 방식)
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version='v1beta') # 버전 명시로 404 방지
        )
        
        # 2. [자동화] 내 계정에서 사용 가능한 모델 목록 확인
        all_models = client.models.list()
        capable_models = [m for m in all_models if 'gemini' in m.name.lower()]
        
        if not capable_models:
            raise Exception("사용 가능한 Gemini 모델을 찾을 수 없습니다.")

        # 이름에 'flash'가 포함된 모델을 우선 선택 (없으면 첫 번째 모델)
        target_model = next((m.name for m in capable_models if 'flash' in m.name.lower()), capable_models[0].name)
        print(f"시스템 자동 감지 모델 사용: {target_model}")

        # 3. 프롬프트 준비 (기존 파일 읽기)
        prompt_template = ""
        if os.path.exists('advisor_set.txt'):
            with open('advisor_set.txt', 'r', encoding='utf-8') as f:
                prompt_template = f.read()
        
        # 한국 시간 생성
        now = datetime.utcnow() + timedelta(hours=9)
        now_str = now.strftime("%Y. %m. %d. %p %I:%M").replace("AM", "오전").replace("PM", "오후")

        # 최종 프롬프트 구성 (JSON 통째로 전달)
        final_prompt = f"""
        {prompt_template}

        [분석할 실시간 데이터]
        {json.dumps(data, ensure_ascii=False, indent=2)}

        [기준 시간]
        {now_str}

        [데이터 매칭 지침]
        1. 헤더 섹션의 KOSPI {{지수}} 위치에는 JSON의 'kospi_value'를 사용합니다.
        2. {{현재시간}} 위치에는 '{now_str}'을 기입하세요.
        3 테이블의 5개 지표는 JSON의 'individual_scores' 배열 순서와 같습니다:
            - score[0]: 1. TDI(125일)
            - score[1]: 2. RSI(14일)
            - score[2]: 3. ADR
            - score[3]: 4. VKOSPI
            - score[4]: 5. PCR
        4. **숫자 표기 (매우 중요)**: 
            - 모든 점수는 JSON에 제공된 그대로 **소수점 둘째 자리까지(예: 45.20, 80.00)** 하나도 빠짐없이 표기하세요.
            - 점수가 정수(예: 80)로 되어 있더라도 반드시 '80.00'과 같은 형식으로 출력해야 합니다.
        5. **색상 클래스 지정 (중요)**:
            - 점수가 20점을 미만이면, 해당 행의 점수와 상태에 'text-red-400' 클래스를 부여하세요.
            - 점수가 40점 미만이면, 'text-orange-400' 클래스를 부여하세요.
            - 점수가 60점 미만이면, 'text-yellow-400' 클래스를 부여하세요.
            - 점수가 80점 미만이면, 'text-emerald-500' 클래스를 부여하세요.
            - 그 외 구간은 'text-primary' 클래스를 부여하세요.
        6. **심리 상태 키워드 생성**:
            - 각 지표의 '상태' 칸에 단순히 '극단적 공포', '공포', '중립', '극심한 탐욕'만 적어도 되지만, 점수를 해석하여 [상태/심리] 형식으로 풍성하게 표현하세요.
            - 0에 가까울수록 극단적 공포, 100에 가까울수록 극심한 탐욕인 점은 참고하세요.
            - 각 지표의 특성(RSI는 과매수/과매도, VKOSPI는 불안/안정 등)에 맞게 창의적으로 짧게 적어주세요.    
        7. 디자인 유지: 원본 디자인의 모든 Tailwind CSS 클래스를 절대 생략하지 마세요.
        8. **수치와 설명이 논리적으로 일치하는지 마지막으로 한 번 더 검토하고 출력해줘. (매우 중요)**
        """
        
        # 4. 결정된 모델로 콘텐츠 생성
        response = client.models.generate_content(
            model=target_model, 
            contents=final_prompt
        )
        
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 결과에서 불필요한 마크다운 제거
        html_content = f"\n" + response.text.replace('```html', '').replace('```', '').strip()

        # 5. 파일 저장 (public/gemini_adv.html)
        public_dir = os.path.join(os.getcwd(), 'public')
        if not os.path.exists(public_dir): os.makedirs(public_dir)
        
        file_path = os.path.join(public_dir, 'gemini_adv.html')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"Gemini 리포트 생성 및 저장 성공: {file_path}")
    except Exception as e:
        print(f"Gemini 리포트 생성 중 에러 발생: {e}")


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

if firestore_initialized:
    try:
        db.collection('korea_index').add(data_to_save)
        print("Firestore에 데이터 저장 완료.")
    except Exception as e:
        print(f"Firestore에 데이터 저장 중 오류 발생: {e}")
else:
    print("Firestore가 초기화되지 않아 데이터 저장을 건너뜁니다.")


# Print data in JSON format for GitHub Actions
output_data = {
    "final_score": score,
    "status_phase": status_obj["phase"],
    "status_description": status_obj["description"],
    "kospi_value": kospi_value,
    "kospi_change_point": kospi_change_point,
    "kospi_change_rate": kospi_change_rate,
    "individual_scores": individual_scores
}

# [추가] 제미나이 리포트 생성 실행
generate_gemini_report(output_data)

if 'GITHUB_OUTPUT' in os.environ:
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write(f"advisor_data={json.dumps(output_data)}\n")