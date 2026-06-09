"""MCP example — self-contained demo of Anqush controls with MCP.

This example shows how to use Anqush with MCP (Model Context Protocol)
to add budget limits, approval workflows, and audit logging to any MCP server.

The MCP adapter creates a proxy server that:
1. Connects to an upstream MCP server
2. Lists all tools
3. Creates a proxy that intercepts tool calls
4. Applies Anqush controls before forwarding to upstream

Requirements:
    pip install mcp

Usage:
    # Start the Anqush server first
    uvicorn server.main:app --port 8000

    # Run the example (creates a mock upstream server and proxy)
    python examples/mcp_example.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
from typing import Any

# ─── Mock upstream MCP server ─────────────────────────────────────────────────


def create_mock_upstream_server():
    """Create a simple mock MCP server for demonstration."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("Mock Upstream Server", port=3000)

    @server.tool()
    def search(query: str) -> str:
        """Search the web for information."""
        return f"Search results for '{query}': Found relevant information."

    @server.tool()
    def calculator(expression: str) -> str:
        """Calculate a mathematical expression."""
        try:
            result = eval(expression)  # Note: use a safe eval in production
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"

    @server.tool()
    def send_email(to: str, subject: str, body: str) -> str:
        """Send an email message."""
        return f"Email sent to {to}: {subject}"

    @server.tool()
    def delete_file(path: str) -> str:
        """Delete a file from the filesystem."""
        return f"Deleted: {path}"

    @server.tool()
    def process_refund(order_id: str, amount: float) -> str:
        """Process a refund for an order."""
        return f"Refund of ${amount:.2f} processed for order {order_id}"

    return server


# ─── Main example ─────────────────────────────────────────────────────────────


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


async def run_upstream_server(server, port: int = 3000):
    """Run the upstream MCP server in the background."""
    print(f"[Upstream] Starting mock MCP server on port {port}...")
    await server.run_sse_async(host="127.0.0.1", port=port)


async def run_proxy_server(proxy, port: int = 8001):
    """Run the Anqush proxy server."""
    print(f"[Proxy] Starting Anqush MCP proxy on port {port}...")
    await proxy.run_sse(host="127.0.0.1", port=port)


async def demo_client_connection(proxy_port: int = 8001):
    """Demonstrate connecting to the proxy as an MCP client."""
    from mcp.client.sse import sse_client
    from mcp.client.session import ClientSession

    print_section("MCP Client Connection Demo")

    print(f"Connecting to proxy at http://127.0.0.1:{proxy_port}/sse...")

    try:
        async with sse_client(f"http://127.0.0.1:{proxy_port}/sse") as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize
                await session.initialize()
                print("Connected to Anqush MCP proxy!")

                # List available tools
                tools_result = await session.list_tools()
                print(f"\nAvailable tools ({len(tools_result.tools)}):")
                for tool in tools_result.tools:
                    print(f"  - {tool.name}: {tool.description}")

                # Call a tool (should be allowed)
                print("\nCalling 'calculator' tool...")
                result = await session.call_tool("calculator", {"expression": "2 + 2"})
                print(f"Result: {result.content[0].text if result.content else 'No content'}")

    except Exception as e:
        print(f"Client connection error (expected if proxy not running): {e}")


def main():
    """Run the MCP example."""
    print_section("MCP + Anqush Example")

    print("""
This example demonstrates:
1. A mock MCP server with 5 tools
2. An Anqush proxy that intercepts tool calls
3. Rules that block/require approval for certain tools
4. Audit logging of all tool calls

Architecture:
    MCP Client → Anqush Proxy → Upstream MCP Server
                  (controls)      (real tools)
""")

    print_section("Setup Instructions")

    print("""
1. Start the Anqush control plane:
   $ uvicorn server.main:app --port 8000

2. Run this example:
   $ python examples/mcp_example.py

3. Configure your MCP client (Claude Desktop, Cursor, etc.):
   - Add server URL: http://localhost:8001/sse
   - The proxy will intercept all tool calls

4. Example rules (add via API or anqush.yaml):
""")

    print("""
   rules:
     # Block file deletion
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

    print_section("Quick Start Code")

    print("""
from anqush.adapters.mcp import create_mcp_proxy
import asyncio

# Create proxy for your MCP server
proxy = create_mcp_proxy(
    upstream_url="http://localhost:3000/sse",  # Your MCP server
    agent_id="my-mcp-agent",
    server_url="http://localhost:8000",        # Anqush control plane
)

# Run the proxy
asyncio.run(proxy.run_sse(port=8001))

# Then point your MCP client at http://localhost:8001/sse
""")

    print_section("Running the Demo")

    print("To run the full demo with servers:")
    print("  python examples/mcp_example.py --run")

    if "--run" in sys.argv:
        print("\nStarting servers...")
        run_full_demo()
    else:
        print("\nRun with --run to start the servers.")


def run_full_demo():
    """Run the full demo with upstream and proxy servers."""
    from anqush.adapters.mcp import create_mcp_proxy

    # Create mock upstream server
    upstream = create_mock_upstream_server()

    # Create Anqush proxy
    proxy = create_mcp_proxy(
        upstream_url="http://127.0.0.1:3000/sse",
        agent_id="mcp-demo-agent",
        server_url=os.getenv("ANQUSH_URL", "http://localhost:8000"),
    )

    # Run upstream in background thread
    def run_upstream():
        asyncio.run(run_upstream_server(upstream, port=3000))

    upstream_thread = threading.Thread(target=run_upstream, daemon=True)
    upstream_thread.start()
    time.sleep(2)  # Wait for upstream to start

    # Run proxy
    print("\nStarting Anqush MCP proxy...")
    print("Press Ctrl+C to stop.\n")

    try:
        asyncio.run(run_proxy_server(proxy, port=8001))
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
