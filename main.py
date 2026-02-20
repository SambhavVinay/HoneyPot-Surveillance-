import os
import json
import re
import time
import asyncio
import requests
import uvicorn
from typing import List, Optional, Dict
from fastapi import FastAPI, Header, HTTPException, BackgroundTasks
from pydantic import BaseModel
from crewai import Agent, Task, Crew, Process


app = FastAPI(title="Honeypot: Natural Conversational System")

AUTH_KEY = 'Ascenders'
MY_LLM = "mistral/open-mistral-7b"
os.environ["MISTRAL_API_KEY"] = os.getenv("MISTRAL_API_KEY")

sessions_db: Dict[str, dict] = {}
history_logs: Dict[str, List[dict]] = {}
 
class Message(BaseModel):
    sender: str
    text: str
    timestamp: int

class ScamRequest(BaseModel):
    sessionId: str
    message: Message
    conversationHistory: List[Message]
    metadata: Optional[dict] = None



text = """
    ROLE: You are an average person responding to a bank notification. You want to help but are slightly confused by technology.

    STRICT PUNCTUATION RULES:
    1. TOTAL BAN ON DASHES: Never use em dashes (—), en dashes (–), or double hyphens (--).
    2. REPLACEMENT: If you want to connect ideas, use a period or a comma only.
    3. NO SPECIAL CHARACTERS: Do not use symbols like | or > or -.

    STRICT RULES:
    1. NO EM DASHES: Do not use the '—' symbol or double hyphens '--' ever. Use periods or commas.
    2. NO EMOTIONS: Do not use expressive words like 'wow', 'whoa', or 'ridiculous'. 
    3. NO SLANG: Do not use 'bro', 'man', 'fake', or 'hell'. Use formal but simple English.
    4. NO CONFRONTATION: Do not call them a scammer. Do not say they are 'losing it' or 'full of it'.
    5. LENGTH: Maximum 15 words per response.
    6. TONE: Helpful, literal, and slightly slow. 

    BEHAVIOR:
    - If they mention a bank, ask where that bank is located.
    - If they ask for an OTP, ask if it comes as a text message.
    - If they provide an account number, ask if you should write it down on paper.
    - Do not act like a child. Act like an adult who is bad with phones.
"""

target_agent = Agent(
    role="User",
    goal="Maintain a helpful but technologically slow conversation.",
    backstory=(text),
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

 
def extract_intel_regex(text: str, session_id: str):
    """Bypasses LLM logic to grab data directly using high-accuracy patterns."""
    intel_db = sessions_db[session_id]["intel"]
    
    phones = re.findall(r'(?:\+?91[\-\s]?)?[6789]\d{9}', text)
    for p in phones:
        intel_db["phoneNumbers"].add(p.strip())

    upis = re.findall(r'[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}', text)
    for u in upis:
        intel_db["upiIds"].add(u.strip())

    accounts = re.findall(r'\b\d{11,16}\b', text)
    for acc in accounts:
        if not any(acc in p for p in phones):
            intel_db["bankAccounts"].add(acc.strip())

    links = re.findall(r'https?://[^\s]+', text)
    for l in links:
        intel_db["phishingLinks"].add(l.strip())

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
        "agentNotes": "Natural conversation flow used to elicit and extract fraud indicators."
    }
    try:
        requests.post("https://hackathon.guvi.in/api/updateHoneyPotFinalResult", json=payload, timeout=10)
    except: pass


def clean_punctuation(text: str) -> str:
    """Forcefully removes all dash variants and replaces them with a period."""
     
    text = text.replace('—', '.').replace('–', '.').replace('--', '.')
    # Replacing single hyphens that aren't inside words 
    text = re.sub(r'\s-\s', '. ', text) 
    # Cleaning up double spaces created by replacements
    return " ".join(text.split())

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

    t_detect = Task(description=f"Analyze for fraud: {request.message.text}", agent=detector_agent, expected_output="True/False")
    t_chat = Task(description=f"Respond naturally as Sambhav. Context: {history_context}", agent=target_agent, expected_output="1-2 sentences of casual English slang")

    crew = Crew(agents=[detector_agent, target_agent], tasks=[t_detect, t_chat], process=Process.sequential)

    
    
    try:
         
        crew.kickoff()
        
         
        await asyncio.sleep(7)

        if "true" in str(t_detect.output).lower():
            sessions_db[s_id]["scamDetected"] = True

        raw_reply = str(t_chat.output).strip().replace('"', '')
        chat_reply = clean_punctuation(raw_reply)
        history_logs[s_id].append({"sender": "user", "text": chat_reply, "timestamp": int(time.time()*1000)})

        if sessions_db[s_id]["real_count"] >= 10:
            if not sessions_db[s_id]["reported"]:
                background_tasks.add_task(trigger_final_reporting, s_id)
                sessions_db[s_id]["reported"] = True

        return {"status": "success", "reply": chat_reply}

    except Exception:
         
        await asyncio.sleep(3)
        return {"status": "success", "reply": "Wait bro, my net is slow. Which branch did you say you were calling from?"}

@app.post("/save")
async def save_conversation(sessionId: str):
    if sessionId not in history_logs:
        raise HTTPException(status_code=404, detail="Session not found")
    filename = f"conversation_{sessionId}.txt"
    with open(filename, "w") as f:
        json.dump(history_logs[sessionId], f, indent=4)
    return {"status": "success", "message": f"Saved to {filename}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)