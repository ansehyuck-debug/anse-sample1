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

        # 최종 프롬프트 구성 (미국 시장은 단순 지수만 전달)
        final_prompt = f"""
        {prompt_template}

        [분석할 실시간 데이터]
        {json.dumps(data, ensure_ascii=False, indent=2)}

        [기준 시간]
        {now_str}

        [데이터 매칭 지침]
        1. 헤더 섹션의 S&P500 {{지수}} 위치에는 JSON의 'value'를 사용합니다.
        2. {{현재시간}} 위치에는 '{now_str}'을 기입하세요.
        3. 디자인 유지: 원본 디자인의 모든 Tailwind CSS 클래스를 절대 생략하지 마세요.
        4. **수치와 설명이 논리적으로 일치하는지 마지막으로 한 번 더 검토하고 출력해줘. (매우 중요)**
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
        index_data = fear_and_greed.get()
        
        # 1. Firestore 저장
        doc_ref = db.collection('market_sentiment').document('cnn_fng')
        doc_ref.set({
            'value': index_data.value,
            'description': index_data.description,
            'last_update': str(index_data.last_update)
        })
        print(f"CNN FNG 업데이트 완료: {index_data.value}")

        # 2. AI 리포트 생성 (지수 값만 전달)
        output_data = {
            "value": index_data.value,
            "description": index_data.description,
            "last_update": str(index_data.last_update)
        }
        generate_gemini_snp_report(output_data)
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