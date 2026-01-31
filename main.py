import os, whisper, asyncio, wave
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from crewai import Agent, Task, Crew, Process

app = FastAPI(title="Real-Time Scam-Baiting Bot")

# 1. Configuration
os.environ["MISTRAL_API_KEY"] = "2smqxCpjSh1yZeAjZUs4yUafsIJbwmbl"
my_llm = "mistral/open-mistral-7b"

# Load the STT model once
stt_model = whisper.load_model("base") 

# 2. The "Counter-Scam" Agent
# This agent's goal is to sound human, confused, and slowly waste the scammer's time.
leg_puller = Agent(
    role="Confused Elderly Person",
    goal="Instantly reply to the scammer with nonsense to waste their time.",
    backstory="You are a 75-year-old person who is very talkative and slow with tech.",
    llm=my_llm,
    allow_delegation=False, # Speed boost: prevents agent from trying to talk to others
    verbose=True
)

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    temp_audio = f"stream_{id(websocket)}.wav"
    
    try:
        while True:
            # Receive full recording after user presses 'n'
            data = await websocket.receive_bytes()
            
            with wave.open(temp_audio, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(data)
            
            # 1. Instant Transcription
            result = stt_model.transcribe(temp_audio, fp16=False)
            scammer_text = result['text'].strip()
            
            if scammer_text:
                print(f"Scammer said: {scammer_text}")
                
                # 2. Generate the "Leg-Pulling" Response
                # We use a single task for maximum speed (instant display)
                bait_task = Task(
                    description=f"REPLY IMMEDIATELY. Scammer said: '{scammer_text}'. Reply as your persona in 1 sentence.",
                    agent=leg_puller,
                    expected_output="A short, funny response."
                )

                # 3. Use a lightweight Crew or just call the agent directly
                crew = Crew(
                    agents=[leg_puller],
                    tasks=[bait_task],
                    process=Process.sequential,
                    cache=False # Speed boost: don't spend time checking old logs
                )
                
                # Kickoff and get result
                agent_reply = crew.kickoff()
                
                # 3. Send text back to terminal instantly
                await websocket.send_text(str(agent_reply))

    except WebSocketDisconnect:
        print("Scammer hung up.")
    finally:
        if os.path.exists(temp_audio): os.remove(temp_audio)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)