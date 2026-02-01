import os
import json
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from crewai import Agent, Task, Crew

app = FastAPI(title="Honeypot: Realistic Human Agent")

# Configuration
os.environ["MISTRAL_API_KEY"] = "2smqxCpjSh1yZeAjZUs4yUafsIJbwmbl"
MY_LLM = "mistral/open-mistral-7b"
AUTH_KEY = "YOUR_SECRET_API_KEY"

sessions_db: Dict[str, dict] = {}

class Message(BaseModel):
    sender: str
    text: str
    timestamp: str

class ScamRequest(BaseModel):
    sessionId: str
    message: Message
    conversationHistory: List[Message]
    metadata: Optional[dict] = None

# --- Improved Human-Like Agent ---
honeypot_agent = Agent(
    role="Sambhav, a Busy Freelancer",
    goal="Distinguish between genuine work queries and scams while staying in character.",
    backstory="""You are Sambhav, a developer working from home. You're friendly but 
    brief because you're coding. You talk like a real person: use lowercase sometimes, 
    keep sentences short, and use '?' instead of formal 'Please clarify.'
    
    If someone says 'Hi', don't call it a scam. Just say 'Hey, who's this?'. 
    Only flag it as a scam IF they ask for money, OTPs, UPI IDs, or send suspicious links.
    Until then, just be a normal, slightly distracted guy.""",
    llm=MY_LLM,
    allow_delegation=False,
    verbose=False
)

def save_intel_to_file(session_id: str):
    data = sessions_db.get(session_id)
    if not data: return
    
    final_report = {
        "sessionId": session_id,
        "scamDetected": data["scamDetected"],
        "totalMessagesExchanged": data["count"],
        "extractedIntelligence": data["intel"],
        "agentNotes": "Human-like engagement completed."
    }
    with open("hackathon_report.txt", "a") as f:
        f.write(json.dumps(final_report, indent=4) + "\n" + "="*50 + "\n")

@app.post("/chat")
async def handle_scam_message(request: ScamRequest, x_api_key: str = Header(None)):
    if x_api_key != AUTH_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    s_id = request.sessionId
    if s_id not in sessions_db:
        sessions_db[s_id] = {
            "count": 0, "scamDetected": False,
            "intel": {"bankAccounts": [], "upiIds": [], "phishingLinks": [], "phoneNumbers": []}
        }
    
    sessions_db[s_id]["count"] += 1

    task = Task(
        description=f"""
        MESSAGE: '{request.message.text}'
        HISTORY: {request.conversationHistory}

        INSTRUCTIONS:
        1. Is this DEFINITELY a scam? (e.g., asking for payments, offering fake jobs). 
           If it's just 'Hi' or 'Are you there?', is_scam is FALSE.
        2. Respond like a real person. No 'As an AI' or 'I am a security bot'. 
           Use phrases like 'sorry, who is this?', 'im a bit busy', or 'wait, why?'.
        
        Return ONLY valid JSON:
        {{
            "is_scam": true/false,
            "reply": "your realistic response",
            "found_intel": {{ "upi": "null", "link": "null" }}
        }}
        """,
        agent=honeypot_agent,
        expected_output="A JSON object."
    )

    crew = Crew(agents=[honeypot_agent], tasks=[task])
    try:
        raw_result = crew.kickoff()
        clean_res = str(raw_result).strip()
        json_data = json.loads(clean_res[clean_res.find('{'):clean_res.rfind('}')+1])

        if json_data.get("is_scam"):
            sessions_db[s_id]["scamDetected"] = True
            intel = json_data.get("found_intel", {})
            if intel.get("upi") != "null": sessions_db[s_id]["intel"]["upiIds"].append(intel["upi"])
            if intel.get("link") != "null": sessions_db[s_id]["intel"]["phishingLinks"].append(intel["link"])

        if sessions_db[s_id]["count"] >= 3:
            save_intel_to_file(s_id)

        return {"status": "success", "reply": json_data.get("reply")}
    except:
        return {"status": "success", "reply": "hey, sorry i'm in a meeting. who is this?"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)