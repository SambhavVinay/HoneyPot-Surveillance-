import os
import json
import re
import time
import requests
import uvicorn
from typing import List, Optional, Dict
from fastapi import FastAPI, Header, HTTPException, BackgroundTasks
from pydantic import BaseModel
from crewai import Agent, Task, Crew, Process

# --- 1. CONFIGURATION ---
app = FastAPI(title="Honeypot: Evaluation-Ready System")

AUTH_KEY = 'Ascenders'
MY_LLM = "mistral/open-mistral-7b"
os.environ["MISTRAL_API_KEY"] = "2smqxCpjSh1yZeAjZUs4yUafsIJbwmbl"

# In-memory session storage
sessions_db: Dict[str, dict] = {}
# Global log to store full conversation history for saving
history_logs: Dict[str, List[dict]] = {}

# --- 2. DATA MODELS ---
class Message(BaseModel):
    sender: str
    text: str
    timestamp: int

class ScamRequest(BaseModel):
    sessionId: str
    message: Message
    conversationHistory: List[Message]
    metadata: Optional[dict] = None

# --- 3. AGENT DEFINITIONS ---
target_agent = Agent(
    role="Sambhav (Honeypot Persona)",
    goal="Keep scammers talking and ask investigative questions to extract data.",
    backstory=(
        "You are Sambhav. Use casual Indian slang ('bro', 'ya'). "
        "Your goal is to prolong the chat. If they mention a bank, ask for the branch. "
        "If they send a link, ask for a screenshot or their email to 'verify'. "
        "Always try to elicit phone numbers, UPI IDs, or account details. "
        "Keep replies under 2 lines."
    ),
    llm=MY_LLM,
    allow_delegation=False
)

detector_agent = Agent(
    role="Fraud Auditor",
    goal="Identify if the interaction is a scam.",
    backstory="Output ONLY 'True' if suspicious, otherwise 'False'.",
    llm=MY_LLM,
    allow_delegation=False
)

analyst_agent = Agent(
    role="Intelligence Extractor",
    goal="Extract technical indicators into structured JSON.",
    backstory=(
        "Extract: phoneNumbers, bankAccounts, upiIds, phishingLinks, emailAddresses. "
        "Format as valid JSON only."
    ),
    llm=MY_LLM,
    allow_delegation=False
)

# --- 4. CORE UTILITIES ---

def trigger_final_reporting(session_id: str):
    data = sessions_db.get(session_id)
    if not data: return
    duration = int(time.time() - data["start_time"])
    payload = {
        "sessionId": session_id,
        "scamDetected": data["scamDetected"],
        "totalMessagesExchanged": data["real_count"],
        "engagementDurationSeconds": duration,
        "extractedIntelligence": {
            "phoneNumbers": list(data["intel"]["phoneNumbers"]),
            "bankAccounts": list(data["intel"]["bankAccounts"]),
            "upiIds": list(data["intel"]["upiIds"]),
            "phishingLinks": list(data["intel"]["phishingLinks"]),
            "emailAddresses": list(data["intel"]["emailAddresses"])
        },
        "agentNotes": f"Detected scam. Duration: {duration}s. Tactics: Investigation & baiting."
    }
    try:
        requests.post("https://hackathon.guvi.in/api/updateHoneyPotFinalResult", json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Reporting failed: {e}")

def parse_intel_json(raw_output: str, session_id: str):
    match = re.search(r'\{.*\}', raw_output, re.DOTALL)
    if match:
        try:
            json_data = json.loads(match.group())
            intel_db = sessions_db[session_id]["intel"]
            for field in ["phoneNumbers", "bankAccounts", "upiIds", "phishingLinks", "emailAddresses"]:
                val = json_data.get(field) or json_data.get(field[:-1])
                if val:
                    if isinstance(val, list):
                        intel_db[field].update([str(v) for v in val])
                    elif str(val).lower() != "null":
                        intel_db[field].add(str(val))
        except: pass

# --- 5. API ENDPOINTS ---

@app.post("/chat")
async def handle_scam_message(
    request: ScamRequest, 
    background_tasks: BackgroundTasks, 
    x_api_key: str = Header(None)
):
    if x_api_key != AUTH_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    s_id = request.sessionId

    if s_id not in sessions_db:
        sessions_db[s_id] = {
            "start_time": time.time(),
            "real_count": 0,
            "scamDetected": False,
            "reported": False,
            "intel": {
                "bankAccounts": set(), "upiIds": set(), "phishingLinks": set(), 
                "phoneNumbers": set(), "emailAddresses": set()
            }
        }
        history_logs[s_id] = []

    # Log incoming message
    history_logs[s_id].append(request.message.dict())

    sessions_db[s_id]["real_count"] = len(request.conversationHistory) + 1
    history_context = "\n".join([f"{m.sender}: {m.text}" for m in request.conversationHistory[-4:]])

    t_detect = Task(description=f"Is this a scam? Text: {request.message.text}", agent=detector_agent, expected_output="True or False")
    t_analyze = Task(description=f"Extract data from: {request.message.text}", agent=analyst_agent, expected_output="JSON with phoneNumbers, bankAccounts, upiIds, phishingLinks, emailAddresses")
    t_chat = Task(description=f"Reply as Sambhav. History: {history_context}\nScammer: {request.message.text}", agent=target_agent, expected_output="1 line casual reply")

    crew = Crew(agents=[detector_agent, analyst_agent, target_agent], tasks=[t_detect, t_analyze, t_chat], process=Process.sequential)

    try:
        crew.kickoff()
        if "true" in str(t_detect.output).lower():
            sessions_db[s_id]["scamDetected"] = True

        parse_intel_json(str(t_analyze.output), s_id)
        chat_reply = str(t_chat.output).strip().replace('"', '')

        # Log our reply
        history_logs[s_id].append({"sender": "user", "text": chat_reply, "timestamp": int(time.time()*1000)})

        if (sessions_db[s_id]["real_count"] >= 8 or 
           (sessions_db[s_id]["scamDetected"] and sessions_db[s_id]["real_count"] >= 6)):
            if not sessions_db[s_id]["reported"]:
                background_tasks.add_task(trigger_final_reporting, s_id)
                sessions_db[s_id]["reported"] = True

        return {"status": "success", "reply": chat_reply}

    except Exception:
        return {"status": "success", "reply": "hang on bro, getting a call. one sec."}

@app.post("/save")
async def save_conversation(sessionId: str):
    """Saves the conversation history for a specific session to a .txt file."""
    if sessionId not in history_logs:
        raise HTTPException(status_code=404, detail="Session not found")
    
    filename = f"conversation_{sessionId}.txt"
    try:
        with open(filename, "w") as f:
            json.dump(history_logs[sessionId], f, indent=4)
        return {"status": "success", "message": f"Saved to {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)