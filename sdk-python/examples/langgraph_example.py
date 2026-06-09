"""LangGraph example — self-contained demo of Anqush controls.

This example shows how to use Anqush with LangGraph's create_react_agent
to add budget limits, approval workflows, and audit logging to any LangGraph agent.

Requirements:
    pip install langgraph langchain-openai

Usage:
    # Start the Anqush server first
    uvicorn server.main:app --port 8000

    # Run the example
    python examples/langgraph_example.py
"""

from __future__ import annotations

import os
from typing import Annotated

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from anqush.adapters.langgraph import wrap_tool_node


# ─── Define tools ─────────────────────────────────────────────────────────────


@tool
def search(query: str) -> str:
    """Search the web for information."""
    # Simulated search results
    return f"Search results for '{query}': Found relevant information about the topic."


@tool
def calculator(expression: str) -> str:
    """Calculate a mathematical expression."""
    try:
        result = eval(expression)  # Note: use a safe eval in production
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {e}"


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email message."""
    print(f"\n[Anqush Example] Sending email to {to}")
    print(f"  Subject: {subject}")
    print(f"  Body: {body[:100]}...")
    return f"Email sent to {to}"


@tool
def delete_file(path: str) -> str:
    """Delete a file from the filesystem."""
    print(f"\n[Anqush Example] DELETING FILE: {path}")
    return f"Deleted: {path}"


@tool
def process_refund(order_id: str, amount: float) -> str:
    """Process a refund for an order."""
    print(f"\n[Anqush Example] Processing refund of ${amount:.2f} for order {order_id}")
    return f"Refund of ${amount:.2f} processed for order {order_id}"


# ─── Main example ─────────────────────────────────────────────────────────────


def main():
    """Run a LangGraph agent with Anqush controls."""
    print("=" * 60)
    print("LangGraph + Anqush Example")
    print("=" * 60)

    # Configure Anqush server URL
    server_url = os.getenv("ANQUSH_URL", "http://localhost:8000")
    agent_id = "langgraph-demo-agent"

    print(f"\nConnecting to Anqush server at: {server_url}")
    print(f"Agent ID: {agent_id}")

    # ── Step 1: Define tools ──
    tools = [search, calculator, send_email, delete_file, process_refund]

    # ── Step 2: Wrap tools with Anqush controls ──
    # This intercepts every tool call and applies:
    # - Block rules (e.g., block delete_file)
    # - Approval rules (e.g., require approval for process_refund > $100)
    # - Budget tracking
    # - Audit logging
    controlled_tools = wrap_tool_node(tools, agent_id=agent_id, server_url=server_url)

    print(f"\nWrapped {len(tools)} tools with Anqush controls:")
    for name in controlled_tools._tool_names:
        print(f"  - {name}")

    # ── Step 3: Create a LangGraph agent ──
    # Note: This requires an OpenAI API key for the LLM
    # In this example, we'll show the setup but won't actually run the agent
    # unless you have OPENAI_API_KEY set

    print("\n" + "-" * 60)
    print("To run this agent with a real LLM:")
    print("-" * 60)
    print("""
    import os
    from langchain_openai import ChatOpenAI

    os.environ["OPENAI_API_KEY"] = "sk-..."

    model = ChatOpenAI(model="gpt-4o")
    graph = create_react_agent(model, controlled_tools)

    # Run the agent
    result = graph.invoke({
        "messages": [HumanMessage(content="Search for LangGraph tutorials")]
    })
    """)

    # ── Step 4: Show what happens with different queries ──
    print("\n" + "=" * 60)
    print("What Anqush controls would do:")
    print("=" * 60)

    # Simulate tool calls through the controlled wrapper
    print("\n1. 'search(query=\"LangGraph\")' → ALLOWED (no rules match)")
    print("2. 'calculator(expression=\"2+2\")' → ALLOWED (no rules match)")
    print("3. 'delete_file(path=\"/etc/passwd\")' → BLOCKED (if block rule exists)")
    print("4. 'process_refund(order_id=\"123\", amount=500)' → APPROVAL REQUIRED (if rule exists)")

    # ── Step 5: Example rules YAML ──
    print("\n" + "=" * 60)
    print("Example anqush.yaml rules:")
    print("=" * 60)
    print("""
    rules:
      # Block dangerous operations
      - name: block-delete
        action: block
        tool: delete_file
        reason: "File deletion is not allowed"

      # Require approval for large refunds
      - name: approve-large-refund
        action: approval
        tool: process_refund
        when:
          amount:
            gt: 100
        reason: "Refunds over $100 require approval"

      # Require approval for any email
      - name: approve-email
        action: approval
        tool: send_email
        reason: "All emails require approval"
    """)

    print("\n" + "=" * 60)
    print("Setup complete! To use with a real LLM:")
    print("1. Start Anqush server: uvicorn server.main:app --port 8000")
    print("2. Create rules via API or anqush.yaml")
    print("3. Set OPENAI_API_KEY and run this script")
    print("=" * 60)


if __name__ == "__main__":
    main()
