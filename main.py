import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import fear_and_greed
from google import genai 
from google.genai import types

# Initialize Flask app
app = Flask(__name__)

# 1. 파이어베이스 인증 (환경변수에서 키 가져오기)
if 'FIREBASE_KEY' not in os.environ:
    print("Warning: FIREBASE_KEY environment variable not set. Firebase operations may fail.")
    key_dict = {} 
else:
    key_dict = json.loads(os.environ['FIREBASE_KEY'])

if key_dict: 
    cred = credentials.Certificate(key_dict)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
else:
    db = None 

def get_fred_data(series_id):
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print(f"Warning: FRED_API_KEY not set. Cannot fetch {series_id}")
        return None
    
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json&sort_order=desc&limit=1"
    try:
        import requests
        response = requests.get(url)
        data = response.json()
        if 'observations' in data and data['observations']:
            obs = data['observations'][0]
            return {
                'value': obs['value'],
                'date': obs['date']
            }
    except Exception as e:
        print(f"Error fetching FRED data for {series_id}: {e}")
    return None

def generate_gemini_snp_report(data):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("에러: GEMINI_API_KEY 환경변수가 없습니다.")
        return

    try:
        # 1. 클라이언트 설정
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version='v1beta')
        )
        
        # 2. 모델 감지
        all_models = client.models.list()
        capable_models = [m for m in all_models if 'gemini' in m.name.lower()]
        if not capable_models:
            raise Exception("사용 가능한 Gemini 모델을 찾을 수 없습니다.")

        target_model = next((m.name for m in capable_models if 'flash' in m.name.lower()), capable_models[0].name)
        print(f"S&P 500 분석 시스템 자동 감지 모델 사용: {target_model}")

        # 3. 프롬프트 준비
        prompt_template = ""
        if os.path.exists('advisor_snp_set.txt'):
            with open('advisor_snp_set.txt', 'r', encoding='utf-8') as f:
                prompt_template = f.read()
        
        now = datetime.utcnow() + timedelta(hours=9)
        now_str = now.strftime("%Y. %m. %d. %p %I:%M").replace("AM", "오전").replace("PM", "오후")

        # 안전하게 데이터를 가져오기 위한 헬퍼
        def safe_get(key):
            val = data.get(key)
            return val if isinstance(val, dict) else {}

        # 최종 프롬프트 구성 (FRED 지표 포함)
        final_prompt = f"""
        {prompt_template}

        [분석할 실시간 데이터]
        - CNN Fear & Greed: {data.get('fng_score', 'N/A')} ({data.get('fng_description', 'N/A')})
        - Economic Indicators (FRED):
          * FED FUNDS RATE: {safe_get('fedfunds').get('value', 'N/A')}% (as of {safe_get('fedfunds').get('date', 'N/A')})
          * VIX: {safe_get('vix').get('value', 'N/A')} (as of {safe_get('vix').get('date', 'N/A')})
          * Non-farm Payrolls: {safe_get('payems').get('value', 'N/A')} (as of {safe_get('payems').get('date', 'N/A')})
          * Unemployment Rate: {safe_get('unrate').get('value', 'N/A')}% (as of {safe_get('unrate').get('date', 'N/A')})
          * 10-Year Treasury Yield: {safe_get('dgs10').get('value', 'N/A')}% (as of {safe_get('dgs10').get('date', 'N/A')})
          * S&P 500 Index: {safe_get('sp500').get('value', 'N/A')} (as of {safe_get('sp500').get('date', 'N/A')})

        [기준 시간]
        {now_str}

        [데이터 매칭 지침]
        1. 헤더 섹션의 S&P500 {{지수}} 위치에는 JSON의 S&P 500 Index 'value'를 사용합니다.
        2. {{현재시간}} 위치에는 '{now_str}'을 기입하세요.
        3. 디자인 유지: 원본 디자인의 모든 Tailwind CSS 클래스를 절대 생략하지 마세요.
        4. **제공된 FRED 경제 지표들(금리, VIX, 고용 등)을 분석 내용에 적극 반영하여 전문적인 인사이트를 제공하세요.**
        5. **금리와 고용 지표는 제공된 날짜를 확인하여 최신 상태인지 언급하세요.**
        6. **수치와 설명이 논리적으로 일치하는지 마지막으로 한 번 더 검토하고 출력해줘. (매우 중요)**
        """
        
        response = client.models.generate_content(
            model=target_model, 
            contents=final_prompt
        )
        
        html_content = "\n" + response.text.replace('```html', '').replace('```', '').strip()

        # 4. 파일 저장
        public_dir = os.path.join(os.getcwd(), 'public')
        if not os.path.exists(public_dir): os.makedirs(public_dir)
        
        file_path = os.path.join(public_dir, 'gemini_snp_adv.html')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"Gemini S&P 500 리포트 생성 및 저장 성공: {file_path}")

        # 5. 다국어 버전 생성
        try:
            translate_prompt = ""
            if os.path.exists('translate_prompt.txt'):
                with open('translate_prompt.txt', 'r', encoding='utf-8') as f:
                    translate_prompt = f.read()
            
            if translate_prompt:
                print("미국 시장 리포트 다국어 번역 요청 중...")
                translation_response = client.models.generate_content(
                    model=target_model,
                    contents=f"{translate_prompt}\n\n[번역할 HTML]\n{html_content}"
                )
                english_html = translation_response.text.replace('```html', '').replace('```', '').strip()
                
                bilingual_content = f"""
<div class="lang-ko">
{html_content}
</div>
<div class="lang-en">
{english_html}
</div>
"""
                bilingual_file_path = os.path.join(public_dir, 'gemini_snp_adv_ko_en.html')
                with open(bilingual_file_path, 'w', encoding='utf-8') as f:
                    f.write(bilingual_content)
                print(f"다국어 S&P 500 리포트 생성 및 저장 성공: {bilingual_file_path}")
        except Exception as e:
            print(f"다국어 리포트 생성 중 에러 발생: {e}")

    except Exception as e:
        print(f"Gemini S&P 500 리포트 생성 중 에러 발생: {e}")

def update_fng():
    if db:
        # 1. CNN F&G 데이터 수집
        index_data = fear_and_greed.get()
        print(f"CNN FNG 수집 완료: {index_data.value}")

        # 2. FRED 경제 지표 수집
        fred_indicators = {
            'fedfunds': get_fred_data('FEDFUNDS'),
            'vix': get_fred_data('VIXCLS'),
            'payems': get_fred_data('PAYEMS'),
            'unrate': get_fred_data('UNRATE'),
            'dgs10': get_fred_data('DGS10'),
            'sp500': get_fred_data('SP500')
        }
        print("FRED 경제 지표 수집 완료")

        # 3. 통합 데이터 구성 및 Firestore 누적 저장 (us_index 컬렉션)
        us_data_to_save = {
            'fng_value': index_data.value,
            'fng_description': index_data.description,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'fedfunds': fred_indicators['fedfunds'],
            'vix': fred_indicators['vix'],
            'payems': fred_indicators['payems'],
            'unrate': fred_indicators['unrate'],
            'dgs10': fred_indicators['dgs10'],
            'sp500': fred_indicators['sp500']
        }
        
        db.collection('us_index').add(us_data_to_save)
        print(f"US 통합 지표 Firestore 저장 완료 (us_index)")

        # 4. AI 리포트 생성용 데이터 구성
        report_data = {
            "fng_score": index_data.value,
            "fng_description": index_data.description,
            "last_update": str(index_data.last_update)
        }
        report_data.update(fred_indicators)
        
        generate_gemini_snp_report(report_data)
    else:
        print("Firestore client not initialized. Skipping FNG update.")


@app.route('/analyze', methods=['POST'])
def analyze_sentiment():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    text = data.get('text')

    if not text:
        return jsonify({"error": "No 'text' field provided"}), 400

    # Placeholder for actual sentiment analysis logic
    # In a real application, you would integrate a sentiment analysis library here
    # For example, using NLTK, TextBlob, or a custom model
    print(f"Received text for analysis: {text}")
    
    # Dummy sentiment result
    sentiment_score = 0.5
    sentiment_label = "neutral"
    if "good" in text.lower() or "happy" in text.lower():
        sentiment_label = "positive"
        sentiment_score = 0.9
    elif "bad" in text.lower() or "sad" in text.lower():
        sentiment_label = "negative"
        sentiment_score = 0.1

    return jsonify({
        "text": text,
        "sentiment": sentiment_label,
        "score": sentiment_score
    })

# Original standalone execution, now integrated with Flask app.run()
if __name__ == "__main__":
    update_fng() # Run the FNG update once on startup
    # For development, you can run the app with 'flask run'
    # or by calling app.run() in a separate script.
    # app.run(debug=True, port=5000)