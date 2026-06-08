"""Basic example: wrap an OpenAI client with Anqush controls."""

import os

import openai

from anqush import wrap_openai

# 1. Create your OpenAI client as normal
raw_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 2. Wrap it with Anqush
client = wrap_openai(
    raw_client,
    agent_id="demo-agent",
    server_url="http://localhost:8000",
)

# 3. Use it normally — controls are applied automatically
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello, world!"}],
)

print(response.choices[0].message.content)
