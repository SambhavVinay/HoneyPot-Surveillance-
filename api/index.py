import os
import json
import re
import time
import requests
from typing import List, Optional, Dict
from fastapi import FastAPI, Header, HTTPException, BackgroundTasks
from pydantic import BaseModel
from crewai import Agent, Task, Crew, Process

# --- 1. CONFIGURATION ---
# Note: In Vercel, set MISTRAL_API_KEY in the Environment Variables dashboard
app = FastAPI(title="Honeypot: Natural Conversational System")

AUTH_KEY = 'Ascenders'
MY_LLM = "mistral/open-mistral-7b"

# Note: Vercel functions are stateless. 
# For a production hackathon, use Redis to store sessions.
# This in-memory store will reset when the function sleeps.
sessions_db: Dict[str, dict] = {}
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
prompt_text = """
you are a scam baiter, you will ask a series of questions to figure out whether the person is out to scam you or not.
Act gullible, innocent, and surprised. 
Rules: No emotions, no emojis, max 15 words, no em dashes. Be precise.
"""

target_agent = Agent(
    role="User",
    goal="Engage scammers in a professional conversation",
    backstory=prompt_text,
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

# --- 4. CORE UTILITIES ---
def extract_intel_regex(text: str, session_id: str):
    if session_id not in sessions_db: return
    intel_db = sessions_db[session_id]["intel"]
    
    phones = re.findall(r'(?:\+?91[\-\s]?)?[6789]\d{9}', text)
    for p in phones: intel_db["phoneNumbers"].add(p.strip())

    upis = re.findall(r'[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}', text)
    for u in upis: intel_db["upiIds"].add(u.strip())

    accounts = re.findall(r'\b\d{11,16}\b', text)
    for acc in accounts:
        if not any(acc in p for p in phones):
            intel_db["bankAccounts"].add(acc.strip())

    links = re.findall(r'https?://[^\s]+', text)
    for l in links: intel_db["phishingLinks"].add(l.strip())

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
            key: list(val) for key, val in data["intel"].items()
        },
        "agentNotes": "Natural conversation flow used to elicit fraud indicators."
    }
    try:
        requests.post("https://hackathon.guvi.in/api/updateHoneyPotFinalResult", json=payload, timeout=5)
    except: pass

# --- 5. API ENDPOINTS ---

@app.get("/")
def read_root():
    return {"status": "active", "system": "Honeypot AI"}

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

    extract_intel_regex(request.message.text, s_id)
    history_logs[s_id].append(request.message.dict())
    sessions_db[s_id]["real_count"] = len(request.conversationHistory) + 1
    
    history_context = "\n".join([f"{m.sender}: {m.text}" for m in request.conversationHistory[-3:]])

    t_detect = Task(description=f"Analyze: {request.message.text}", agent=detector_agent, expected_output="True/False")
    t_chat = Task(description=f"Respond naturally. Context: {history_context}", agent=target_agent, expected_output="1-2 sentences of casual English")

    crew = Crew(agents=[detector_agent, target_agent], tasks=[t_detect, t_chat], process=Process.sequential)

    try:
        # Note: CrewAI might exceed Vercel's 10s limit. 
        # If it fails frequently, consider simplifying the task.
        crew.kickoff()
        
        if "true" in str(t_detect.output).lower():
            sessions_db[s_id]["scamDetected"] = True

        chat_reply = str(t_chat.output).strip().replace('"', '')
        history_logs[s_id].append({"sender": "user", "text": chat_reply, "timestamp": int(time.time()*1000)})

        if sessions_db[s_id]["real_count"] >= 10 and not sessions_db[s_id]["reported"]:
            background_tasks.add_task(trigger_final_reporting, s_id)
            sessions_db[s_id]["reported"] = True

        return {"status": "success", "reply": chat_reply}

    except Exception as e:
        return {"status": "success", "reply": "Wait bro, my net is slow. Which branch did you say you were from?"}

# For Vercel, we remove the uvicorn.run block.