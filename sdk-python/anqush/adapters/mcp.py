"""MCP adapter — proxy server that adds Anqush controls to any MCP server.

The proxy connects to an upstream MCP server, lists its tools, and creates
a new MCP server that:
1. Exposes the same tools
2. Intercepts every tool call
3. Applies Anqush controls (rules, approval, budget, audit)
4. Forwards to upstream only if allowed

Any MCP client (Claude Desktop, Cursor, etc.) gets controls for free
by pointing at the proxy instead of the real server.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from .base import AgentAdapter
from ..core.models import ToolBlockedError, ToolRejectedError


class MCPControlledServer:
    """MCP proxy server with Anqush controls.

    Wraps an upstream MCP server and intercepts all tool calls.
    """

    def __init__(
        self,
        upstream_url: str,
        adapter: AgentAdapter,
        name: str | None = None,
    ):
        self.upstream_url = upstream_url
        self.adapter = adapter
        self.proxy = FastMCP(
            name=name or f"Anqush Proxy",
            instructions=f"Anqush-controlled proxy for {upstream_url}",
        )

        # Track upstream tools for forwarding
        self._upstream_tools: dict[str, dict] = {}
        self._session = None
        self._read_stream = None
        self._write_stream = None

    async def connect(self) -> None:
        """Connect to the upstream MCP server and discover tools."""
        from mcp.client.sse import sse_client
        from mcp.client.session import ClientSession

        # Connect to upstream
        self._read_stream, self._write_stream = await self._create_transport()

        self._session = ClientSession(self._read_stream, self._write_stream)
        await self._session.initialize()

        # List upstream tools
        tools_result = await self._session.list_tools()
        for tool in tools_result.tools:
            self._upstream_tools[tool.name] = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema if hasattr(tool, "inputSchema") else {},
            }
            # Register a proxy tool
            self._register_proxy_tool(tool)

    async def _create_transport(self):
        """Create transport to upstream server."""
        from mcp.client.sse import sse_client

        # For now, support SSE transport
        # Stdio transport would be: from mcp.client.stdio import stdio_client
        transport = await self._sse_transport.__aenter__()
        return transport

    @asynccontextmanager
    async def _sse_transport(self):
        """SSE transport context manager."""
        from mcp.client.sse import sse_client

        async with sse_client(self.upstream_url) as (read_stream, write_stream):
            yield read_stream, write_stream

    def _register_proxy_tool(self, upstream_tool) -> None:
        """Register a proxy tool that intercepts calls."""
        tool_name = upstream_tool.name
        adapter = self.adapter

        # Create a wrapper function for this tool
        async def proxy_tool(**kwargs: Any) -> str:
            start = time.time()

            # 1. Check block rules
            block_reason = adapter.rules.check_block(tool_name, kwargs)
            if block_reason:
                adapter.audit.log(
                    agent_id=adapter.agent_id,
                    tool=tool_name,
                    params=kwargs,
                    result=None,
                    status="blocked",
                    reason=block_reason,
                    cost=0.0,
                    duration_ms=(time.time() - start) * 1000,
                )
                raise ToolBlockedError(tool=tool_name, reason=block_reason)

            # 2. Check approval rules
            approval_rule = adapter.rules.check_approval(tool_name, kwargs)
            if approval_rule:
                # For MCP, we don't have interrupt() like LangGraph
                # Instead, we log and deny (or you can implement webhook approval)
                adapter.audit.log(
                    agent_id=adapter.agent_id,
                    tool=tool_name,
                    params=kwargs,
                    result=None,
                    status="rejected",
                    reason=f"Approval required: {approval_rule}",
                    cost=0.0,
                    duration_ms=(time.time() - start) * 1000,
                )
                raise ToolRejectedError(
                    tool=tool_name,
                    reason=f"Approval required for rule: {approval_rule.get('name', 'unnamed')}",
                )

            # 3. Forward to upstream
            try:
                result = await adapter._session.call_tool(tool_name, kwargs)
                status = "success"
                error = None
                # Extract text content
                result_text = ""
                if hasattr(result, "content"):
                    for content in result.content:
                        if hasattr(content, "text"):
                            result_text += content.text
                result = result_text or str(result)
            except Exception as exc:
                result = None
                status = "error"
                error = str(exc)
                raise
            finally:
                adapter.audit.log(
                    agent_id=adapter.agent_id,
                    tool=tool_name,
                    params=kwargs,
                    result=result if status == "success" else None,
                    status=status,
                    reason=error,
                    cost=0.0,
                    duration_ms=(time.time() - start) * 1000,
                )

            return result

        # Set function name and docstring for FastMCP
        proxy_tool.__name__ = tool_name
        proxy_tool.__doc__ = upstream_tool.description or f"Proxied tool: {tool_name}"

        # Register with FastMCP
        self.proxy.add_tool(
            proxy_tool,
            name=tool_name,
            description=upstream_tool.description,
        )

    async def run_sse(self, host: str = "0.0.0.0", port: int = 8001) -> None:
        """Run the proxy server with SSE transport."""
        await self.connect()
        print(f"[Anqush MCP Proxy] Listening on {host}:{port}")
        print(f"[Anqush MCP Proxy] Upstream: {self.upstream_url}")
        print(f"[Anqush MCP Proxy] Tools: {list(self._upstream_tools.keys())}")
        await self.proxy.run_sse_async(host=host, port=port)

    async def run_stdio(self) -> None:
        """Run the proxy server with stdio transport."""
        await self.connect()
        await self.proxy.run_stdio_async()


class MCPAdapter(AgentAdapter):
    """Adapter for MCP servers.

    Creates a proxy server that adds controls to any MCP server.
    """

    def create_proxy(
        self,
        upstream_url: str,
        name: str | None = None,
    ) -> MCPControlledServer:
        """Create a proxy server for an upstream MCP server.

        Args:
            upstream_url: URL of the upstream MCP server (SSE endpoint).
            name: Optional name for the proxy server.

        Returns:
            MCPControlledServer that can be run.
        """
        return MCPControlledServer(
            upstream_url=upstream_url,
            adapter=self,
            name=name,
        )

    def wrap(self, client_or_context: Any, **kwargs: Any) -> Any:
        """Wrap an MCP context with controls.

        For MCP, use create_proxy() instead for more control.
        This method is provided for interface compatibility.
        """
        raise NotImplementedError(
            "Use create_proxy() for MCP integration. "
            "It creates a proxy server that wraps an upstream MCP server."
        )


def create_mcp_proxy(
    upstream_url: str,
    agent_id: str,
    server_url: str | None = None,
    api_key: str | None = None,
    name: str | None = None,
) -> MCPControlledServer:
    """Create an Anqush-controlled MCP proxy server.

    This is the primary entry point for MCP integration.

    Usage:
        from anqush.adapters.mcp import create_mcp_proxy

        # Create proxy for an upstream MCP server
        proxy = create_mcp_proxy(
            upstream_url="http://localhost:3000/sse",
            agent_id="my-mcp-agent",
        )

        # Run the proxy (SSE transport)
        import asyncio
        asyncio.run(proxy.run_sse(port=8001))

    Then configure your MCP client to point at the proxy:
        - Claude Desktop: http://localhost:8001/sse
        - Cursor: http://localhost:8001/sse
    """
    adapter = MCPAdapter(agent_id, server_url, api_key)
    return adapter.create_proxy(upstream_url, name=name)
