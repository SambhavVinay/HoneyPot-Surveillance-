import os
import whisper # You'll need: pip install openai-whisper
from fastapi import FastAPI, HTTPException, UploadFile, File
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

app = FastAPI(title="Voice Scam Detection API")

# 1. Configuration
os.environ["MISTRAL_API_KEY"] = "2smqxCpjSh1yZeAjZUs4yUafsIJbwmbl"
my_llm = "mistral/open-mistral-7b"
MY_EMAIL = "teamdopameme@gmail.com"
MY_APP_PASSWORD = "obqdsxzodjcirwhd"

# Load the STT model once at startup
stt_model = whisper.load_model("base") 

# 2. Email Tool (Same as before)
@tool("send_email_report")
def send_email_report(content: str):
    """Sends the scam analysis report via email."""
    import smtplib
    from email.message import EmailMessage
    msg = EmailMessage()
    msg.set_content(content)
    msg['Subject'] = '🚨 Voice Scam Analysis Report'
    msg['From'] = MY_EMAIL
    msg['To'] = MY_EMAIL
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(MY_EMAIL, MY_APP_PASSWORD)
            smtp.send_message(msg)
        return "Email sent successfully!"
    except Exception as e:
        return f"Failed: {e}"

# 3. Agents (Tweaked for Voice Scam context)
voice_analyst = Agent(
    role="Voice Content Analyst",
    goal="Identify verbal scam triggers like OTP requests, bank impersonation, or 'KYC' threats.",
    backstory="You are an expert in vishing (voice phishing) tactics and social engineering.",
    llm=my_llm,
    verbose=True
)

verdict_officer = Agent(
    role="Cybersecurity Official",
    goal="Provide a final 'SCAM' or 'GENUINE' verdict on the call transcript.",
    backstory="Security specialist trained to spot fraudulent phone calls.",
    llm=my_llm,
    verbose=True
)

email_agent = Agent(
    role="Alert Communicator",
    goal="Send the report to teamdopameme@gmail.com.",
    backstory="Alert delivery specialist.",
    llm=my_llm,
    tools=[send_email_report],
    verbose=True
)

@app.get("/")
async def health():
    return {"message":"backend of crew ai working and alive."}
# 4. API Endpoint for Audio
@app.post("/analyze-call")
async def analyze_call(file: UploadFile = File(...)):
    # Save temp audio file
    temp_filename = f"temp_{file.filename}"
    with open(temp_filename, "wb") as buffer:
        buffer.write(await file.read())

    try:
        # Step 1: Transcribe Audio to Text
        print("Transcribing audio...")
        result = stt_model.transcribe(temp_filename)
        transcript = result['text']
        
        # Step 2: Kickoff the Crew with the transcript
        analysis_task = Task(
            description=f"Analyze this call transcript for scam indicators: \n\n {transcript}",
            agent=voice_analyst,
            expected_output="A summary of suspicious verbal cues."
        )

        verdict_task = Task(
            description="Give a SCAM/GENUINE verdict. Specifically look for requests for OTPs or urgent KYC.",
            agent=verdict_officer,
            expected_output="Final Verdict Report."
        )

        email_task = Task(
            description="Email the final verdict to the user.",
            agent=email_agent,
            expected_output="Confirmation of email."
        )

        crew = Crew(
            agents=[voice_analyst, verdict_officer, email_agent],
            tasks=[analysis_task, verdict_task, email_task],
            process=Process.sequential
        )

        crew_output = crew.kickoff()
        
        # Cleanup
        os.remove(temp_filename)

        return {
            "status": "success",
            "transcript": transcript,
            "verdict": str(crew_output)
        }

    except Exception as e:
        if os.path.exists(temp_filename): os.remove(temp_filename)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)