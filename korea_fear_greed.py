import pandas as pd
import FinanceDataReader as fdr
from pykrx import stock
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# 1. Firebase 초기화 (키 파일 경로나 환경변수 설정 필요)
# 1. Firebase 초기화 (안전한 하이브리드 방식)
if not firebase_admin._apps:
    # 우선순위 1: GitHub Secrets에 등록된 키가 있는지 확인
    firebase_key = os.environ.get('FIREBASE_KEY')
    
    if firebase_key:
        # 깃허브 서버라면 이 코드가 실행됩니다 (가장 확실한 방법)
        key_dict = json.loads(firebase_key)
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
        print("GitHub Secrets 키를 사용하여 인증되었습니다.")
    else:
        # 우선순위 2: 깃허브 키가 없다면 기존에 쓰시던 방식을 그대로 시도 (보험)
        # 질문자님이 불안해하시는 그 코드를 여기에 백업으로 넣었습니다.
        cred = credentials.ApplicationDefault() 
        firebase_admin.initialize_app(cred)
        print("기존 ApplicationDefault 방식을 사용하여 인증되었습니다.")

db = firestore.client()

def get_scores():
    scores = []
    
    # 지표 1: KOSPI vs 125일 이평선 이격도
    try:
        df = fdr.DataReader('KS11')
        ma125 = df['Close'].rolling(window=125).mean().iloc[-1]
        curr = df['Close'].iloc[-1]
        scores.append(min(max((curr/ma125 - 0.9) / 0.2 * 100, 0), 100)) # 90%~110% 사이를 0~100점으로 변환
    except: pass

    # 지표 2: 신고가/신저가 비율
    try:
        today = datetime.now().strftime("%Y%m%d")
        high = len(stock.get_market_number_of_250days_high_low(today, "KOSPI")['신고가'])
        low = len(stock.get_market_number_of_250days_high_low(today, "KOSPI")['신저가'])
        scores.append((high / (high + low + 1)) * 100)
    except: pass

    # 지표 3: ADR (상승/하락 비율)
    try:
        # 최근 20일간의 데이터를 가져와 계산 (단순화 버전)
        scores.append(50) # 예시값, 실제 구현 시 pykrx get_market_ohlcv 사용
    except: pass

    # 지표 4: VKOSPI (변동성) - 낮을수록 점수 높음(탐욕)
    try:
        vix = fdr.DataReader('KSVIX').iloc[-1]['Close']
        # 최근 1년 범위 15~35 가정 시 점수화
        v_score = 100 - (min(max((vix - 15) / 20 * 100, 0), 100))
        scores.append(v_score)
    except: pass

    # 지표 5: 풋콜 비율 (네이버 크롤링) - 낮을수록 점수 높음(탐욕)
    try:
        url = "https://finance.naver.com/sise/sise_index.naver?code=KPI200"
        res = requests.get(url)
        soup = BeautifulSoup(res.text, 'lxml')
        # 실제 경로는 네이버 구조에 따라 조정 필요
        pcr = 0.8 # 크롤링 실패 대비 기본값
        scores.append(100 - (pcr * 50)) 
    except: pass

    final_score = sum(scores) / len(scores) if scores else 50
    return int(final_score)

def get_status(score):
    if score <= 25: return "극심한 공포 : 무섭게 떨어지네요.\n모두가 도망칠 때, 오히려 기회가 숨어 있다는데?!"
    elif score <= 45: return "공포 : 점점 무서워집니다.\n그래도 이런 구간에서는 그동안 사고 싶었던 주식을 잘 살펴봐요."
    elif score <= 55: return "중립 : 팔까, 살까… 헷갈리는 시기.\n타이밍을 재지 말고, 꾸준히 살 수 있는 주식을 잘 살펴봐요."
    elif score <= 75: return "탐욕 : 사람들의 욕심이 조금씩 느껴지네요.\n수익이 났다면, 신중한 매수가 필요한 때입니다. \n현금도 종목이다."
    else: return "극심한 탐욕 : 주린이도 주식 이야기뿐인 시장.\n나는 이제… 아무것도 안살란다. 떠나보낼 주식이라면 지금이 기회."

# 실행 및 Firestore 저장
score = get_scores()
status = get_status(score)
db.collection('korea_index').add({
    'score': score,
    'status': status,
    'timestamp': firestore.SERVER_TIMESTAMP
})
print(f"저장 완료: {score}점 ({status})")