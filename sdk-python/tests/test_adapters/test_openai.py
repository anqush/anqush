"""Tests for anqush.adapters.openai."""

import pytest
from unittest.mock import MagicMock, patch

from anqush.adapters.openai import OpenAIAdapter, OpenAIControlledClient, wrap_openai
from anqush.adapters.base import ControlledTool


class TestOpenAIAdapter:
    """Tests for OpenAIAdapter."""

    def test_creation(self, server_url, agent_id):
        adapter = OpenAIAdapter(agent_id, server_url)
        assert adapter.agent_id == agent_id
        assert adapter.server_url == server_url

    def test_wrap(self, server_url, agent_id):
        adapter = OpenAIAdapter(agent_id, server_url)
        mock_client = MagicMock()
        controlled = adapter.wrap(mock_client)

        assert isinstance(controlled, OpenAIControlledClient)
        assert controlled._client is mock_client


class TestOpenAIControlledClient:
    """Tests for OpenAIControlledClient."""

    def test_getattr_proxies_to_client(self, server_url, agent_id):
        adapter = OpenAIAdapter(agent_id, server_url)
        mock_client = MagicMock()
        mock_client.custom_attr = "value"

        controlled = OpenAIControlledClient(mock_client, adapter)
        assert controlled.custom_attr == "value"

    def test_wrap_tools_callable(self, server_url, agent_id):
        adapter = OpenAIAdapter(agent_id, server_url)
        mock_client = MagicMock()

        controlled = OpenAIControlledClient(mock_client, adapter)

        def my_tool(x: str) -> str:
            return x

        wrapped = controlled._wrap_tools([my_tool])
        assert len(wrapped) == 1
        assert isinstance(wrapped[0], ControlledTool)

    def test_wrap_tools_dict_schema(self, server_url, agent_id):
        adapter = OpenAIAdapter(agent_id, server_url)
        mock_client = MagicMock()

        controlled = OpenAIControlledClient(mock_client, adapter)

        tool_schema = {
            "type": "function",
            "function": {"name": "search", "description": "Search"},
        }
        wrapped = controlled._wrap_tools([tool_schema])
        assert len(wrapped) == 1
        assert wrapped[0] is tool_schema  # Dict schemas passed through

    def test_wrap_tools_none(self, server_url, agent_id):
        adapter = OpenAIAdapter(agent_id, server_url)
        mock_client = MagicMock()

        controlled = OpenAIControlledClient(mock_client, adapter)
        assert controlled._wrap_tools(None) is None

    def test_chat_completions_create(self, server_url, agent_id):
        adapter = OpenAIAdapter(agent_id, server_url)
        mock_client = MagicMock()

        # Mock usage
        mock_usage = MagicMock()
        mock_usage.total_tokens = 100

        mock_response = MagicMock()
        mock_response.usage = mock_usage

        mock_client.chat.completions.create.return_value = mock_response

        controlled = OpenAIControlledClient(mock_client, adapter)

        result = controlled.chat_completions_create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert result is mock_response
        mock_client.chat.completions.create.assert_called_once()


class TestWrapOpenAI:
    """Tests for wrap_openai function."""

    def test_wrap_openai(self, server_url, agent_id):
        mock_client = MagicMock()
        controlled = wrap_openai(mock_client, agent_id, server_url)

        assert isinstance(controlled, OpenAIControlledClient)
        assert controlled._client is mock_client
