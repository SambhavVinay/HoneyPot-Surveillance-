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

app = FastAPI(title="Honeypot: Natural Conversational System")


AUTH_KEY = 'Ascenders'

MY_LLM = "mistral/open-mistral-7b"

os.environ["MISTRAL_API_KEY"] = "2smqxCpjSh1yZeAjZUs4yUafsIJbwmbl"


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

text = """
        you are a scam baiter, you willl ask a series of questions to figure out weather the person is out to scam you or not.
            here are the possible triggers for a scam
        1.Unsolicited "Win" Notification: You receive a message claiming you won a prize (e.g., Apple iPad, Amazon gift card) for a contest you never entered.
        2.Urgency to Act Now: Messages pressure you to click a link immediately or lose the prize.
        3.Requests for Fees/Personal Info: Legitimate contests don't ask for payment, bank details, or Social Security numbers to receive a prize.
        4.Suspicious Links: Links may look like official websites but are actually designed to steal login credentials or download malware.
        5.Unexpected "Shipment" Fees: A text claims you won a high-value item (like a phone) but requires a small fee for shipping

        A few DONTs to consider while giving out the reply as the user
        1. DO NOT show/express emotions on text
        2. DO NOT use emojis in texts
        3. AVOID long messages, anything more than 15 words
        4. AVOID em dashes completely

        Here are a few traits the user should have while replying:
        1. Act gullible and innocent
        2. Act very surprised and innocent to the scammers replies
        3. Do not over explain yourself, stick to a single point and be confident
        4. stop being very underconfident
        5. speak precisely and to the point, do not elaborate unless needed
        
       """

target_agent = Agent(

    role="User",

    goal="Engage scammers in a professional conversation",

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


# --- 4. CORE UTILITIES ---


def extract_intel_regex(text: str, session_id: str):

    """Bypasses LLM logic to grab data directly using high-accuracy patterns."""

    intel_db = sessions_db[session_id]["intel"]

    

    # Phone Numbers (Matches +91-..., 91..., or 10 digits)

    phones = re.findall(r'(?:\+?91[\-\s]?)?[6789]\d{9}', text)

    for p in phones:

        intel_db["phoneNumbers"].add(p.strip())


    # UPI IDs (Captures anything@bank, etc)

    upis = re.findall(r'[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}', text)

    for u in upis:

        intel_db["upiIds"].add(u.strip())


    # Bank Accounts (Focusing on 11-16 digit strings)

    # We use a lookahead/lookbehind to ensure we aren't just grabbing parts of phone numbers

    accounts = re.findall(r'\b\d{11,16}\b', text)

    for acc in accounts:

        if not any(acc in p for p in phones):

            intel_db["bankAccounts"].add(acc.strip())


    # Links

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


    # Run extraction on every incoming message

    extract_intel_regex(request.message.text, s_id)

    

    history_logs[s_id].append(request.message.dict())

    sessions_db[s_id]["real_count"] = len(request.conversationHistory) + 1

    

    history_context = "\n".join([f"{m.sender}: {m.text}" for m in request.conversationHistory[-3:]])


    t_detect = Task(description=f"Analyze for fraud: {request.message.text}", agent=detector_agent, expected_output="True/False")

    t_chat = Task(description=f"Respond naturally as Sambhav. Context: {history_context}", agent=target_agent, expected_output="1-2 sentences of casual English slang")


    crew = Crew(agents=[detector_agent, target_agent], tasks=[t_detect, t_chat], process=Process.sequential)


    try:

        crew.kickoff()

        

        if "true" in str(t_detect.output).lower():

            sessions_db[s_id]["scamDetected"] = True


        chat_reply = str(t_chat.output).strip().replace('"', '')

        history_logs[s_id].append({"sender": "user", "text": chat_reply, "timestamp": int(time.time()*1000)})


        # Report after 10 messages or if scam is confirmed

        if sessions_db[s_id]["real_count"] >= 10:

            if not sessions_db[s_id]["reported"]:

                background_tasks.add_task(trigger_final_reporting, s_id)

                sessions_db[s_id]["reported"] = True


        return {"status": "success", "reply": chat_reply}


    except Exception:

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