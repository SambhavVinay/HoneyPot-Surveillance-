import logging
import os
from crewai import Task, Agent, LLM, Crew
from crewai_tools import ScrapeWebsiteTool
from dotenv import load_dotenv

# 1. Suppress LiteLLM and other library logging
logging.getLogger("litellm").setLevel(logging.CRITICAL)

load_dotenv()

# Optional: Disable telemetry for a cleaner start
os.environ["OTEL_SDK_DISABLED"] = "true"

llm = LLM(
    model="mistral/mistral-small-latest", 
    api_key=os.getenv("MISTRAL_API_KEY")
)

tool = ScrapeWebsiteTool(website_url="https://rudrarvu.vercel.app/")

agent = Agent(
    role="Article Summarizer",
    goal="Summarize the website content in under 100 words.",
    backstory="You are an expert at distilling long web pages into concise summaries.",
    tools=[tool],
    llm=llm,
    verbose=False,  # <--- Set this to False for clean output
    max_iter=3,
    allow_delegation=False
)

task = Task(
    description="Read the website content and provide a summary under 100 words.",
    agent=agent,
    expected_output="A summary of the website in under 100 words."
)

crew = Crew(agents=[agent], tasks=[task])

try:
    result = crew.kickoff()
    print("\n--- Generated Response ---")
    print(result.raw) # Use .raw to get just the string result
except Exception as e:
    print(f"\nCaught an error: {e}")