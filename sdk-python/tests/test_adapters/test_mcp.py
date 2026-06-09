"""Tests for anqush.adapters.mcp."""

import pytest
from unittest.mock import MagicMock

from anqush.adapters.mcp import MCPAdapter, MCPControlledServer, create_mcp_proxy


class TestMCPAdapter:
    """Tests for MCPAdapter."""

    def test_creation(self, server_url, agent_id):
        adapter = MCPAdapter(agent_id, server_url)
        assert adapter.agent_id == agent_id
        assert adapter.server_url == server_url

    def test_create_proxy(self, server_url, agent_id):
        adapter = MCPAdapter(agent_id, server_url)
        proxy = adapter.create_proxy("http://localhost:3000/sse")

        assert isinstance(proxy, MCPControlledServer)
        assert proxy.upstream_url == "http://localhost:3000/sse"

    def test_create_proxy_with_name(self, server_url, agent_id):
        adapter = MCPAdapter(agent_id, server_url)
        proxy = adapter.create_proxy("http://localhost:3000/sse", name="My Proxy")

        assert proxy.proxy.name == "My Proxy"

    def test_wrap_raises(self, server_url, agent_id):
        adapter = MCPAdapter(agent_id, server_url)
        with pytest.raises(NotImplementedError):
            adapter.wrap(None)


class TestMCPControlledServer:
    """Tests for MCPControlledServer."""

    def test_creation(self, server_url, agent_id):
        adapter = MCPAdapter(agent_id, server_url)
        server = MCPControlledServer(
            upstream_url="http://localhost:3000/sse",
            adapter=adapter,
        )

        assert server.upstream_url == "http://localhost:3000/sse"
        assert server.adapter is adapter
        assert server.proxy is not None

    def test_creation_with_name(self, server_url, agent_id):
        adapter = MCPAdapter(agent_id, server_url)
        server = MCPControlledServer(
            upstream_url="http://localhost:3000/sse",
            adapter=adapter,
            name="Test Proxy",
        )

        assert server.proxy.name == "Test Proxy"


class TestCreateMCPProxy:
    """Tests for create_mcp_proxy function."""

    def test_create_mcp_proxy(self, server_url, agent_id):
        proxy = create_mcp_proxy(
            upstream_url="http://localhost:3000/sse",
            agent_id=agent_id,
            server_url=server_url,
        )

        assert isinstance(proxy, MCPControlledServer)
        assert proxy.upstream_url == "http://localhost:3000/sse"
        assert proxy.adapter.agent_id == agent_id

    def test_create_mcp_proxy_with_name(self, server_url, agent_id):
        proxy = create_mcp_proxy(
            upstream_url="http://localhost:3000/sse",
            agent_id=agent_id,
            server_url=server_url,
            name="My MCP Proxy",
        )

        assert proxy.proxy.name == "My MCP Proxy"


class TestMCPProxyToolRegistration:
    """Tests for tool registration on the proxy."""

    def test_register_proxy_tool(self, server_url, agent_id):
        from mcp.types import Tool as MCPTool

        adapter = MCPAdapter(agent_id, server_url)
        server = MCPControlledServer(
            upstream_url="http://localhost:3000/sse",
            adapter=adapter,
        )

        # Create a mock upstream tool
        mock_tool = MCPTool(
            name="search",
            description="Search the web",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}},
        )

        server._register_proxy_tool(mock_tool)
        # Tool should be registered on the FastMCP proxy
        assert server.proxy._tool_manager._tools.get("search") is not None

    def test_proxy_tool_has_correct_metadata(self, server_url, agent_id):
        from mcp.types import Tool as MCPTool

        adapter = MCPAdapter(agent_id, server_url)
        server = MCPControlledServer(
            upstream_url="http://localhost:3000/sse",
            adapter=adapter,
        )

        mock_tool = MCPTool(
            name="calculator",
            description="Calculate math",
            inputSchema={"type": "object"},
        )

        server._register_proxy_tool(mock_tool)
        registered_tool = server.proxy._tool_manager._tools.get("calculator")
        assert registered_tool is not None
        assert registered_tool.description == "Calculate math"
