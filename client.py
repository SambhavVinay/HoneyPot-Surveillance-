import requests
import uuid
from datetime import datetime

API_URL = "http://127.0.0.1:8000/chat"
API_KEY = "YOUR_SECRET_API_KEY"

def start_chat():
    session_id = f"user-{uuid.uuid4().hex[:6]}"
    history = []
    
    print(f"--- Conversation Started (ID: {session_id}) ---")
    print("Test with a 'Hello' first to see if it still thinks it's a scam.")

    while True:
        text = input("\nMe: ").strip()
        if text.lower() in ['q', 'exit']: break
        if not text: continue

        payload = {
            "sessionId": session_id,
            "message": {
                "sender": "scammer",
                "text": text,
                "timestamp": datetime.now().isoformat()
            },
            "conversationHistory": history
        }

        try:
            response = requests.post(API_URL, json=payload, headers={"x-api-key": API_KEY})
            if response.status_code == 200:
                reply = response.json().get("reply")
                print(f"Sambhav (Agent): {reply}")
                
                history.append(payload["message"])
                history.append({"sender": "user", "text": reply, "timestamp": datetime.now().isoformat()})
            else:
                print(f"Server Error: {response.status_code}")
        except Exception as e:
            print(f"Connection failed: {e}")

if __name__ == "__main__":
    start_chat()