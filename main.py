import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request, jsonify
import fear_and_greed # Assuming this is an external package or was a local file

# Initialize Flask app
app = Flask(__name__)

# 1. 파이어베이스 인증 (환경변수에서 키 가져오기)
# Ensure FIREBASE_KEY is set in your environment variables
# Example: export FIREBASE_KEY='{"type": "service_account", ...}'
if 'FIREBASE_KEY' not in os.environ:
    print("Warning: FIREBASE_KEY environment variable not set. Firebase operations may fail.")
    # For local development without env var, you might temporarily hardcode it or use a file path
    # key_dict = json.loads(open('path/to/your/serviceAccountKey.json').read())
    # For now, let's just make sure it doesn't crash if not found.
    # We will assume it will be set correctly in a deployment environment.
    key_dict = {} # Placeholder to prevent immediate error, but Firebase will likely fail init
else:
    key_dict = json.loads(os.environ['FIREBASE_KEY'])

if key_dict: # Only initialize if key_dict is not empty (i.e., env var was set)
    cred = credentials.Certificate(key_dict)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
else:
    db = None # Firestore client will not be available

# This function might need to be adjusted or removed if fear_and_greed is not available
# For now, commenting out the call to fear_and_greed.get()
def update_fng():
    if db:
        # 2. 지수 가져오기 - Temporarily disabled as fear_and_greed is not found
        index_data = fear_and_greed.get()
        print("Skipping FNG update: fear_and_greed module not available or FIREBASE_KEY not set.")
        # Placeholder for index_data if fear_and_greed is not used
        # index_data = type('obj', (object,), {'value': 'N/A', 'description': 'N/A', 'last_update': 'N/A'})()

        # 3. 파이어베이스 Firestore에 저장
        doc_ref = db.collection('market_sentiment').document('cnn_fng')
        doc_ref.set({
            'value': index_data.value,
            'description': index_data.description,
            'last_update': str(index_data.last_update)
        })
        print(f"업데이트 완료: {index_data.value}")
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