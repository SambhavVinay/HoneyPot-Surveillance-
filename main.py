import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

# 1. Setup FastAPI
app = FastAPI(title="Phishing Detection API")

# 2. Define Request Model
class EmailInput(BaseModel):
    email_text: str

# 3. Environment & Config
os.environ["MISTRAL_API_KEY"] = "2smqxCpjSh1yZeAjZUs4yUafsIJbwmbl"
my_llm = "mistral/open-mistral-7b"
MY_EMAIL = "teamdopameme@gmail.com"
MY_APP_PASSWORD = "obqdsxzodjcirwhd"

# 4. Tool with Scope-Safe Imports
@tool("send_email_report")
def send_email_report(content: str):
    """Sends the phishing analysis report via email."""
    import smtplib
    from email.message import EmailMessage
    
    msg = EmailMessage()
    msg.set_content(content)
    msg['Subject'] = '🚨 Phishing Analysis Report'
    msg['From'] = MY_EMAIL
    msg['To'] = MY_EMAIL

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(MY_EMAIL, MY_APP_PASSWORD)
            smtp.send_message(msg)
        return "Email sent successfully!"
    except Exception as e:
        return f"Failed to send email: {e}"

# 5. Define Agents (Global or inside endpoint)
content_analyst = Agent(
    role="Email Content Analyst",
    goal="Identify psychological triggers in the email body.",
    backstory="Expert in social engineering analysis.",
    llm=my_llm,
    verbose=True
)

link_inspector = Agent(
    role="Link & URL Specialist",
    goal="Extract and analyze all URLs in the email.",
    backstory="Specialist in deceptive URL detection.",
    llm=my_llm,
    verbose=True
)

verdict_officer = Agent(
    role="Cybersecurity Official",
    goal="Provide a final 'PHISHING' or 'GENUINE' verdict.",
    backstory="Final decision maker on security threats.",
    llm=my_llm,
    verbose=True
)

file_manager = Agent(
    role="Report Formatter",
    goal="Extract only the Verdict, High-Risk Links, and Action Steps.",
    backstory="Administrative assistant specializing in technical documentation.",
    llm=my_llm,
    verbose=True
)

email_agent = Agent(
    role="Cybersecurity Communicator",
    goal="Send the final report via email.",
    backstory="Stakeholder management and alert delivery specialist.",
    llm=my_llm,
    tools=[send_email_report],
    verbose=True
)

# 6. API Endpoint
@app.post("/detect-phishing")
async def detect_phishing(input_data: EmailInput):
    try:
        
        # Define Tasks inside the route to use the dynamic input
        analysis_task = Task(
            description=f"Review the email content: \n\n {input_data.email_text} \n\n Look for urgency and threats.",
            agent=content_analyst,
            expected_output="Summary of red flags."
        )

        link_task = Task(
            description=f"Extract all links from: \n\n {input_data.email_text}",
            agent=link_inspector,
            expected_output="Risk assessment of URLs.",
            async_execution=True  # <--- This runs at the same time as analysis_task
        )

        verdict_task = Task(
            description="Determine if this email is phishing based on previous findings.",
            agent=verdict_officer,
            expected_output="Final Report: [Verdict: PHISHING/GENUINE]"
        )

        save_task = Task(
            description="Summarize the final verdict into a concise 'Key Findings' format.",
            agent=file_manager,
            expected_output="Concise summary.",
            output_file="api_phishing_summary.txt"
        )

        email_task = Task(
            description=f"Email the summary to {MY_EMAIL}.",
            agent=email_agent,
            expected_output="Confirmation email sent."
        )

        # Create Crew
        crew = Crew(
            agents=[content_analyst, link_inspector, verdict_officer, file_manager, email_agent],
            tasks=[analysis_task, link_task, verdict_task, save_task, email_task],
            process=Process.sequential
        )

        # Execute
        result = crew.kickoff()
        
        return {
            "status": "success",
            "verdict": str(result)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)