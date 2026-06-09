"""Tests for anqush.adapters.base."""

import pytest
from unittest.mock import MagicMock

from anqush.adapters.base import AgentAdapter, ControlledTool
from anqush.core.models import ToolBlockedError, ToolRejectedError


class TestControlledTool:
    """Tests for ControlledTool."""

    def test_creation(self, server_url):
        tool = ControlledTool(
            func=lambda **kw: "result",
            name="test_tool",
            agent_id="test-agent",
            rules=MagicMock(),
            approvals=MagicMock(),
            audit=MagicMock(),
        )
        assert tool.name == "test_tool"
        assert tool.agent_id == "test-agent"

    def test_call_success(self, server_url):
        mock_rules = MagicMock()
        mock_rules.check_block.return_value = None
        mock_rules.check_approval.return_value = None

        mock_func = MagicMock(return_value="result")
        tool = ControlledTool(
            func=mock_func,
            name="test_tool",
            agent_id="test-agent",
            rules=mock_rules,
            approvals=MagicMock(),
            audit=MagicMock(),
        )

        result = tool(x=1)
        assert result == "result"
        mock_func.assert_called_once_with(x=1)

    def test_call_blocked(self, server_url):
        mock_rules = MagicMock()
        mock_rules.check_block.return_value = "Not allowed"

        tool = ControlledTool(
            func=MagicMock(),
            name="test_tool",
            agent_id="test-agent",
            rules=mock_rules,
            approvals=MagicMock(),
            audit=MagicMock(),
        )

        with pytest.raises(ToolBlockedError) as exc_info:
            tool(x=1)
        assert exc_info.value.tool == "test_tool"

    def test_call_rejected(self, server_url):
        mock_rules = MagicMock()
        mock_rules.check_block.return_value = None
        mock_rules.check_approval.return_value = {"name": "needs-approval"}

        mock_approvals = MagicMock()
        mock_approvals.request.return_value = False

        tool = ControlledTool(
            func=MagicMock(),
            name="test_tool",
            agent_id="test-agent",
            rules=mock_rules,
            approvals=mock_approvals,
            audit=MagicMock(),
        )

        with pytest.raises(ToolRejectedError) as exc_info:
            tool(x=1)
        assert exc_info.value.tool == "test_tool"

    def test_call_approved(self, server_url):
        mock_rules = MagicMock()
        mock_rules.check_block.return_value = None
        mock_rules.check_approval.return_value = {"name": "needs-approval"}

        mock_approvals = MagicMock()
        mock_approvals.request.return_value = True

        mock_func = MagicMock(return_value="approved result")
        tool = ControlledTool(
            func=mock_func,
            name="test_tool",
            agent_id="test-agent",
            rules=mock_rules,
            approvals=mock_approvals,
            audit=MagicMock(),
        )

        result = tool(x=1)
        assert result == "approved result"

    def test_call_error(self, server_url):
        mock_rules = MagicMock()
        mock_rules.check_block.return_value = None
        mock_rules.check_approval.return_value = None

        def failing_func(**kw):
            raise ValueError("Something went wrong")

        tool = ControlledTool(
            func=failing_func,
            name="test_tool",
            agent_id="test-agent",
            rules=mock_rules,
            approvals=MagicMock(),
            audit=MagicMock(),
        )

        with pytest.raises(ValueError):
            tool(x=1)
        # Audit should still be called
        tool.audit.log.assert_called_once()


class TestAgentAdapter:
    """Tests for AgentAdapter (via concrete subclass)."""

    def test_creation(self, server_url, agent_id):
        # Create a concrete subclass for testing
        class TestAdapter(AgentAdapter):
            def wrap(self, client_or_context, **kwargs):
                return client_or_context

        adapter = TestAdapter(agent_id, server_url)
        assert adapter.agent_id == agent_id
        assert adapter.server_url == server_url

    def test_controlled_tool(self, server_url, agent_id):
        class TestAdapter(AgentAdapter):
            def wrap(self, client_or_context, **kwargs):
                return client_or_context

        adapter = TestAdapter(agent_id, server_url)
        func = lambda **kw: "result"
        tool = adapter.controlled_tool(func, name="my_tool")

        assert isinstance(tool, ControlledTool)
        assert tool.name == "my_tool"
        assert tool.agent_id == agent_id

    def test_controlled_tool_default_name(self, server_url, agent_id):
        class TestAdapter(AgentAdapter):
            def wrap(self, client_or_context, **kwargs):
                return client_or_context

        adapter = TestAdapter(agent_id, server_url)

        def my_function():
            pass

        tool = adapter.controlled_tool(my_function)
        assert tool.name == "my_function"
