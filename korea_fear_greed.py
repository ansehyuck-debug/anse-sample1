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

    # 지표 3: ADR (상승/하락 비율) - pykrx 사용 (등락률 컬럼명 수정 및 todate 인자 추가)
    try:
        df_change = pd.DataFrame()
        for i in range(5): # 지난 5일간 데이터를 시도
            target_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
            try:
                # fromdate와 todate 인자 모두 target_date로 지정
                df_temp = stock.get_market_price_change_by_ticker(fromdate=target_date, todate=target_date, market="KOSPI")
                if not df_temp.empty:
                    df_change = df_temp
                    print("지표 3 (ADR): %s 데이터 사용." % target_date)
                    break
                else:
                    print("지표 3 (ADR): %s 데이터 비어있음. 다음 날짜로 재시도." % target_date)
            except Exception as e_inner:
                print("지표 3 (ADR): %s 데이터 조회 실패. 재시도. 오류: %s" % (target_date, str(e_inner)))
        
        if df_change.empty:
            raise ValueError("ADR 데이터를 5일 동안 찾지 못했습니다.")

        adv = (df_change['등락률'] > 0).sum()
        dec = (df_change['등락률'] < 0).sum()

        adr_score_raw = (adv / dec) * 100 if dec != 0 else (100 if adv > 0 else 50)
        
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

    # 지표 4: VKOSPI (변동성) - pykrx 사용 (pykrx ONLY, FDR 관련 코드 모두 제거)
    try:
        # 넉넉한 기간 (예: 90일) 데이터를 가져와서 20일 윈도우 계산에 사용
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d") 
        end_date = datetime.now().strftime("%Y%m%d")
        
        # VKOSPI 코드 "1003" 사용
        vkospi_df = stock.get_index_ohlcv(start_date, end_date, "1003") 
        
        if vkospi_df.empty:
            raise ValueError("pykrx에서 VKOSPI 데이터를 찾을 수 없습니다. (데이터프레임 비어있음)")

        # '종가' 컬럼 사용 (사용자 지침에 따라 확인)
        vix = vkospi_df['종가'].iloc[-1]
        
        window_size = min(len(vkospi_df), 20) # 20일 윈도우, 데이터 부족 시 조정
        if window_size > 0:
            low = vkospi_df['종가'].rolling(window=window_size).min().iloc[-1]
            high = vkospi_df['종가'].rolling(window=window_size).max().iloc[-1]
            if high - low == 0:
                v_score = 50
            else:
                v_score = 100 * (1 - (vix - low) / (high - low))
        else:
            v_score = 50

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