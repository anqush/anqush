"""Example: tool call that requires human approval."""

import os

import openai

from anqush import wrap_openai


def send_email(to: str, subject: str, body: str) -> str:
    """Send an email. This will require approval if configured."""
    return f"Email sent to {to}: {subject}"


raw_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

client = wrap_openai(
    raw_client,
    agent_id="approval-demo",
    server_url="http://localhost:8000",
)

# Simulate a tool call that goes through Anqush controls
# In a real agent, this would be called by the LLM via function calling
wrapped_tool = client._wrap_tools([send_email])[0]

try:
    result = wrapped_tool(to="boss@company.com", subject="Urgent", body="We need to talk")
    print(f"Result: {result}")
except Exception as e:
    print(f"Blocked/Rejected: {e}")
