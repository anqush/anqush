"""Tests for anqush.adapters.langgraph."""

import pytest
from unittest.mock import MagicMock

from anqush.adapters.langgraph import LangGraphAdapter, ControlledToolNode, wrap_tool_node


@pytest.fixture
def dummy_tool():
    """Create a dummy LangGraph tool for testing."""
    from langchain_core.tools import tool

    @tool
    def search(query: str) -> str:
        """Search for information."""
        return f"Results for: {query}"

    return search


@pytest.fixture
def dummy_tool_2():
    """Create a second dummy tool."""
    from langchain_core.tools import tool

    @tool
    def calculator(expression: str) -> str:
        """Calculate an expression."""
        return str(eval(expression))

    return calculator


class TestLangGraphAdapter:
    """Tests for LangGraphAdapter."""

    def test_creation(self, server_url, agent_id):
        adapter = LangGraphAdapter(agent_id, server_url)
        assert adapter.agent_id == agent_id
        assert adapter.server_url == server_url

    def test_wrap_tool_node(self, server_url, agent_id, dummy_tool):
        adapter = LangGraphAdapter(agent_id, server_url)
        node = adapter.wrap_tool_node([dummy_tool])

        assert isinstance(node, ControlledToolNode)
        assert "search" in node._tool_names


class TestControlledToolNode:
    """Tests for ControlledToolNode."""

    def test_creation(self, server_url, agent_id, dummy_tool):
        adapter = LangGraphAdapter(agent_id, server_url)
        node = ControlledToolNode([dummy_tool], adapter=adapter)

        assert "search" in node._tool_names
        assert node._node is not None

    def test_creation_multiple_tools(self, server_url, agent_id, dummy_tool, dummy_tool_2):
        adapter = LangGraphAdapter(agent_id, server_url)
        node = ControlledToolNode([dummy_tool, dummy_tool_2], adapter=adapter)

        assert len(node._tool_names) == 2
        assert "search" in node._tool_names
        assert "calculator" in node._tool_names

    def test_wrapper_attached(self, server_url, agent_id, dummy_tool):
        adapter = LangGraphAdapter(agent_id, server_url)
        node = ControlledToolNode([dummy_tool], adapter=adapter)

        assert node._node._wrap_tool_call is not None

    def test_getattr_proxies_to_node(self, server_url, agent_id, dummy_tool):
        adapter = LangGraphAdapter(agent_id, server_url)
        node = ControlledToolNode([dummy_tool], adapter=adapter)

        # Should proxy to underlying ToolNode
        assert hasattr(node._node, "tools_by_name")


class TestWrapToolNode:
    """Tests for wrap_tool_node function."""

    def test_wrap_tool_node(self, server_url, agent_id, dummy_tool):
        node = wrap_tool_node([dummy_tool], agent_id=agent_id, server_url=server_url)

        assert isinstance(node, ControlledToolNode)
        assert "search" in node._tool_names

    def test_wrap_tool_node_custom_name(self, server_url, agent_id, dummy_tool):
        node = wrap_tool_node(
            [dummy_tool], agent_id=agent_id, server_url=server_url, name="my_tools"
        )

        assert node._node.name == "my_tools"


class TestControlledToolNodeWrapper:
    """Tests for the wrapper function inside ControlledToolNode."""

    def test_wrapper_allows_unblocked_tool(self, server_url, agent_id, dummy_tool):
        adapter = LangGraphAdapter(agent_id, server_url)
        # No rules = everything allowed
        node = ControlledToolNode([dummy_tool], adapter=adapter)

        # Get the wrapper function
        wrapper = node._make_wrapper()
        assert callable(wrapper)

    def test_wrapper_blocks_tool(self, server_url, agent_id, dummy_tool):
        from langchain_core.messages import ToolMessage

        adapter = LangGraphAdapter(agent_id, server_url)
        adapter._rules = []
        # Manually set rules on the rules engine
        adapter.rules._rules = [
            {"name": "block-search", "action": "block", "tool": "search", "reason": "Blocked"}
        ]

        node = ControlledToolNode([dummy_tool], adapter=adapter)
        wrapper = node._make_wrapper()

        # Create a mock request
        mock_request = MagicMock()
        mock_request.tool_call = {"name": "search", "args": {"query": "test"}, "id": "123"}

        mock_execute = MagicMock()

        result = wrapper(mock_request, mock_execute)
        assert isinstance(result, ToolMessage)
        assert "Blocked" in result.content
        mock_execute.assert_not_called()
