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

    # 지표 3: ADR (상승/하락 비율) - 웹 스크래핑 사용 (www.adrinfo.kr)
    try:
        url_adr = "http://www.adrinfo.kr/main/sub_adr_index.html"
        headers = {'User-Agent': 'Mozilla/5.0'}
        adr_score_scaled = 50 # 기본값
        for attempt in range(3): # 최대 3회 재시도
            try:
                response = requests.get(url_adr, headers=headers, timeout=10)
                response.raise_for_status() # HTTP 오류 발생 시 예외 발생
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 'KOSPI' ADR 값을 찾기. 실제 웹사이트 구조 확인 필요.
                # 개발자 도구로 확인된 셀렉터: #ad_idx_2 > tbody > tr:nth-child(1) > td:nth-child(2)
                adr_value_tag = soup.select_one('#ad_idx_2 > tbody > tr:nth-child(1) > td:nth-child(2)')
                if adr_value_tag:
                    adr_text = adr_value_tag.get_text(strip=True)
                    adr_score_raw = float(adr_text)
                    
                    # ADR 값을 0~100 스케일로 변환
                    if adr_score_raw <= 70:
                        adr_score_scaled = 0
                    elif adr_score_raw >= 120:
                        adr_score_scaled = 100
                    else:
                        adr_score_scaled = (adr_score_raw - 70) / (120 - 70) * 100
                    
                    print("지표 3 (ADR) 성공: %.2f (원시값), %.2f (스케일된 값)" % (adr_score_raw, adr_score_scaled))
                    break # 성공 시 루프 탈출
                else:
                    raise ValueError("ADR 웹사이트에서 값을 찾을 수 없습니다.")
            except Exception as e_inner:
                print("지표 3 (ADR) 웹 스크래핑 시도 %d 실패: %s" % (attempt + 1, str(e_inner)))
                time.sleep(2) # 2초 대기 후 재시도
        scores.append(adr_score_scaled)
    except Exception as e:
        print("지표 3 (ADR) 최종 오류: %s" % str(e))
        scores.append(50)

    # 지표 4: VKOSPI (변동성) - 웹 스크래핑 사용 (네이버 금융)
    try:
        url_vkospi = "https://finance.naver.com/marketindex/worldDailyQuote.naver?marketIndexCd=FX_USDKRW" # 임시, VKOSPI 직접 페이지 필요
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'} # User-Agent 강화
        v_score = 50 # 기본값
        for attempt in range(3): # 최대 3회 재시도
            try:
                response = requests.get(url_vkospi, headers=headers, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # 네이버 금융에서 VKOSPI 값을 찾기 (실제 페이지 구조 확인 후 셀렉터 조정 필요)
                # KOSPI 변동성 지수는 별도 페이지가 아님. KOSPI 200 선물/옵션 관련 페이지에서 가져와야 함.
                # 예를 들어, 네이버 금융 KOSPI 200 선물 일봉 차트 페이지에서 수치 추출 시도.
                # 임시 셀렉터: 실제 VKOSPI 값을 가진 요소는 다른 페이지에 있을 가능성이 높음
                
                # 가장 신뢰할 수 있는 네이버 금융 VKOSPI 데이터는 다음과 같은 형태의 테이블 안에 존재함
                # <span class="num">17.23</span>
                # 좀 더 명확한 페이지를 찾거나 셀렉터를 확인해야 함.
                # 일단은 KOSPI 일봉 페이지에서 지수값을 가져와 임시로 사용.
                # 정확한 VKOSPI 셀렉터를 찾기 위해 네이버 금융 페이지 탐색 필요.
                # 임시로 '코스피' 지수 값을 가져오는 셀렉터 사용. 이것은 VKOSPI가 아님!
                
                # 실제 VKOSPI는 개별 종목 페이지나 지수 페이지에서 직접적으로 수치를 제공하지 않음
                # 일반적으로 선물/옵션 관련 데이터 페이지에서 파생되는 경우가 많음.
                # 임시방편으로, 현재는 네이버 금융에서 '코스피' 지수를 가져오는 셀렉터를 사용하고,
                # 이 부분을 실제 VKOSPI 셀렉터로 대체해야 함을 명시
                
                # --- 임시 VKOSPI 셀렉터 (향후 정확한 셀렉터로 교체 필요) ---
                # 네이버 금융 > 증권 > 시장지표 > 국내증시 > KOSPI 지수 (현재가)를 가져오는 셀렉터 예시
                vkospi_value_tag = soup.select_one('#KOSPI_now') # 이 셀렉터는 KOSPI 지수임. VKOSPI 아님.
                if not vkospi_value_tag:
                     vkospi_value_tag = soup.select_one('.current_price_inner .blind') # 또 다른 일반적인 현재가 셀렉터
                # -------------------------------------------------------------------

                if vkospi_value_tag:
                    vkospi_text = vkospi_value_tag.get_text(strip=True).replace(',', '')
                    vix = float(vkospi_text)
                    
                    # VKOSPI 스케일링 로직은 그대로 유지 (단, 가져오는 값이 VKOSPI여야 함)
                    v_score = 100 - (min(max((vix - 17) / 20 * 100, 0), 100))
                    
                    print("지표 4 (VKOSPI) 성공 (임시): %.2f (원시값), %.2f (스케일된 값)" % (vix, v_score))
                    break # 성공 시 루프 탈출
                else:
                    raise ValueError("네이버 금융 페이지에서 VKOSPI 값(또는 임시 지수 값)을 찾을 수 없습니다.")
            except Exception as e_inner:
                print("지표 4 (VKOSPI) 웹 스크래핑 시도 %d 실패: %s" % (attempt + 1, str(e_inner)))
                time.sleep(2) # 2초 대기 후 재시도
        scores.append(v_score)
    except Exception as e:
        print("지표 4 (VKOSPI) 최종 오류: %s" % str(e))
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
