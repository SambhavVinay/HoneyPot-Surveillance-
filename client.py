import requests
import uuid
import time

API_URL = "http://127.0.0.1:7860"
API_KEY = 'Ascenders'

def start_chat():
    session_id = f"test-{uuid.uuid4().hex[:6]}"
    history = []
    
    print(f"--- Fast Response Honeypot (ID: {session_id}) ---")
    print("Type 'exit' to generate report and quit.")

    while True:
        try:
            text = input("\nMe: ").strip()
            if text.lower() in ['q', 'exit']:
                print("Finalizing results...")
                requests.post(f"{API_URL}/save_report", json={"sessionId": session_id})
                break
            if not text: continue

            payload = {
                "sessionId": session_id,
                "message": {"sender": "scammer", "text": text, "timestamp": int(time.time() * 1000)},
                "conversationHistory": history,
                "metadata": {"channel": "Chat", "language": "English", "locale": "IN"}
            }

            # Timeout increased slightly but Process.parallel makes it feel faster
            response = requests.post(f"{API_URL}/chat", json=payload, headers={"x-api-key": API_KEY}, timeout=40)
            
            if response.status_code == 200:
                reply = response.json().get("reply")
                print(f"Sambhav: {reply}")
                history.append(payload["message"])
                history.append({"sender": "user", "text": reply, "timestamp": int(time.time() * 1000)})
            else:
                print(f"Error: {response.status_code}")

        except KeyboardInterrupt:
            requests.post(f"{API_URL}/save_report", json={"sessionId": session_id})
            break
        except Exception as e:
            print(f"Failed: {e}")

if __name__ == "__main__":
    start_chat()