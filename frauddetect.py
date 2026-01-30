import os
from crewai import Agent, Task, Crew, Process
from  crewai.tools import tool
import smtplib
from email.message import EmailMessage
# 1. Set the environment variable (Use your NEW key here)
os.environ["MISTRAL_API_KEY"] = "2smqxCpjSh1yZeAjZUs4yUafsIJbwmbl"

# 2. Define the LLM configuration for Mistral
# Use 'mistral/mistral-large-latest' or 'mistral/open-mistral-7b'
 
MY_EMAIL = "teamdopameme@gmail.com"
MY_APP_PASSWORD = "obqdsxzodjcirwhd"

@tool("send_email_report")
def send_email_report(content: str):
    """Sends the phishing analysis report via email."""
    msg = EmailMessage()
    msg.set_content(content)
    msg['Subject'] = '🚨 Phishing Analysis Report'
    msg['From'] = MY_EMAIL
    msg['To'] = "teamdopameme@gmail.com"

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(MY_EMAIL, MY_APP_PASSWORD)
            smtp.send_message(msg)
        return "Email sent successfully!"
    except Exception as e:
        return f"Failed to send email: {e}"

my_llm = "mistral/mistral-large-latest"
# 3. Pass the 'llm' parameter to every agent
content_analyst = Agent(
    role="Email Content Analyst",
    goal="Identify psychological triggers in the email body.",
    backstory="Expert in social engineering analysis.",
    llm=my_llm,  # <--- CRITICAL: Explicitly set the LLM
    verbose=True,
    allow_delegation=False
)

link_inspector = Agent(
    role="Link & URL Specialist",
    goal="Extract and analyze all URLs in the email.",
    backstory="Specialist in deceptive URL detection.",
    llm=my_llm,  # <--- CRITICAL: Explicitly set the LLM
    verbose=True,
    allow_delegation=False
)

verdict_officer = Agent(
    role="Cybersecurity Official",
    goal="Provide a final 'PHISHING' or 'GENUINE' verdict.",
    backstory="Final decision maker on security threats.",
    llm=my_llm,  # <--- CRITICAL: Explicitly set the LLM
    verbose=True)

# --- Tasks ---
file_manager = Agent(
    role="Report Formatter",
    goal="Extract only the Verdict, High-Risk Links, and immediate Action Steps into a concise format.",
    backstory="You are an administrative assistant specializing in technical documentation and brevity.",
    llm=my_llm,
    verbose=True
)

email_agent = Agent(
    role="Cybersecurity Communicator",
    goal="Send the final report to the designated email address.",
    backstory="You ensure that the technical findings reach the right stakeholders immediately.",
    llm=my_llm,
    tools=[send_email_report],
    verbose=True
)

email_task = Task(
    description="Take the final summary from the Report Formatter and email it to teamdopameme@gmail.com using the send_email_report tool.",
    agent=email_agent,
    expected_output="Confirmation that the email was sent."
)

save_task = Task(
    description="Summarize the final verdict into a 'Key Findings' format and ignore the detailed explanations.",
    agent=file_manager,
    expected_output="A concise summary containing: Verdict, Suspicious Domains, and Action Items.",
    output_file="concise_phishing_summary.txt" # This saves the summary specifically
)

analysis_task = Task(
    description=(
        "Review the following email content: \n\n {email_text} \n\n"
        "Look for: 1. Sense of urgency 2. Requests for sensitive info 3. Unusual tone."
    ),
    agent=content_analyst,
    expected_output="A summary of psychological red flags found in the text."
)

link_task = Task(
    description=(
        "Extract all links from the email: \n\n {email_text} \n\n"
        "Identify if any links are masked, use IP addresses instead of domains, or lead to suspicious sites."
    ),
    agent=link_inspector,
    expected_output="A list of all links found and a risk assessment for each."
)

verdict_task = Task(
    description="Based on the content analysis and link inspection, determine if this email is a phishing attempt.",
    agent=verdict_officer,
    expected_output="Final Report: [Verdict: PHISHING/GENUINE] followed by a brief 'Why' and 'Action Steps'."
)

# --- Crew ---

# Add the new agent and task to the list
phishing_crew = Crew(
    agents=[content_analyst, link_inspector, verdict_officer, file_manager, email_agent],
    tasks=[analysis_task, link_task, verdict_task, save_task, email_task],
    process=Process.sequential
)

# --- Execution ---

test_email = """
From: sambhavvinay20054@gmail.com
Subject: Follow up: Looking for oppurtunities as a student.

 Dear Deepak sir,

I am writing to thank you for your talk and the guidance you shared during the GDG TechSprint at RV University. Your insights were incredibly valuable to those of us navigating the competition.

I served as the lead for the team behind Reclaim, which placed in the Top 10. As requested, I have included my profiles below:
LinkedIn: https://www.linkedin.com/in/sambhavvinay/

GitHub: https://github.com/SambhavVinay

App's MVP: 
https://appdistribution.firebase.google.com/testerapps/1:680513043824:android:e47cd2b2f46fff28a623b5/releases/6gbfcvk0s7tao?utm_source=firebase-console

I would appreciate the opportunity to discuss our technical approach further if you have any feedback or upcoming opportunities. Thank you again for your time. 
"""

result = phishing_crew.kickoff(inputs={'email_text': test_email})

print("\n=== Final Security Verdict ===\n")
print(result)