import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
import fear_and_greed

# 1. 파이어베이스 인증 (환경변수에서 키 가져오기)
key_dict = json.loads(os.environ['FIREBASE_KEY'])
cred = credentials.Certificate(key_dict)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()

def update_fng():
    # 2. 지수 가져오기
    index_data = fear_and_greed.get()
    
    # 3. 파이어베이스 Firestore에 저장
    doc_ref = db.collection('market_sentiment').document('cnn_fng')
    doc_ref.set({
        'value': index_data.value,
        'description': index_data.description,
        'last_update': str(index_data.last_update)
    })
    print(f"업데이트 완료: {index_data.value}")

if __name__ == "__main__":
    update_fng()
