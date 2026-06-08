"""Example: agent with a budget limit enforced by Anqush."""

import os

import openai

from anqush import wrap_openai

raw_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# This agent has a $0.50 session budget configured on the server
client = wrap_openai(
    raw_client,
    agent_id="budget-demo",
    server_url="http://localhost:8000",
)

# First call should succeed
print("Call 1...")
resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say hello briefly"}],
)
print(f"  OK. Session spend: ${client.session_spend:.4f}")

# Many more calls will eventually hit the budget
for i in range(2, 20):
    print(f"Call {i}...")
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say hello briefly"}],
        )
        print(f"  OK. Session spend: ${client.session_spend:.4f}")
    except Exception as e:
        print(f"  BLOCKED: {e}")
        break
