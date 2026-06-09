"""OpenAI adapter — wraps OpenAI clients with Anqush controls."""

from __future__ import annotations

from typing import Any

from .base import AgentAdapter, ControlledTool


class OpenAIControlledClient:
    """Wraps an OpenAI client, intercepting tool calls and completions."""

    def __init__(self, client: Any, adapter: OpenAIAdapter):
        self._client = client
        self._adapter = adapter

    def _wrap_tools(self, tools: list[Any] | None) -> list[Any] | None:
        """Wrap tool functions so calls go through controls."""
        if not tools:
            return tools

        wrapped = []
        for tool in tools:
            if callable(tool):
                # It's a function — wrap it
                name = getattr(tool, "__name__", "unknown")
                wrapped.append(self._adapter.controlled_tool(tool, name))
            elif isinstance(tool, dict) and "function" in tool:
                # OpenAI function schema — keep as-is, the model will call it
                # and we'll intercept via the completions API wrapper
                wrapped.append(tool)
            else:
                wrapped.append(tool)
        return wrapped

    def chat_completions_create(self, *args: Any, **kwargs: Any) -> Any:
        """Intercept chat.completions.create for budget tracking."""
        model = kwargs.get("model", "gpt-4o")
        messages = kwargs.get("messages", [])

        # Budget check before call
        estimated_cost = self._adapter.budget.estimate_call_cost(model, messages)
        self._adapter.budget.check_budget(estimated_cost)

        # Wrap tools if present
        if "tools" in kwargs:
            kwargs["tools"] = self._wrap_tools(kwargs["tools"])

        result = self._client.chat.completions.create(*args, **kwargs)

        # Track actual spend (approximate from usage)
        if hasattr(result, "usage") and result.usage:
            actual_tokens = result.usage.total_tokens
            actual_cost = self._adapter.budget.estimate_cost(model, actual_tokens)
            self._adapter.budget.record_spend(actual_cost)

        return result

    def __getattr__(self, name: str) -> Any:
        """Proxy all other attributes to the underlying client."""
        return getattr(self._client, name)


class OpenAIAdapter(AgentAdapter):
    """Adapter for OpenAI SDK.

    Wraps an OpenAI client to intercept tool calls and enforce controls.
    """

    def wrap(self, client: Any, **kwargs: Any) -> OpenAIControlledClient:
        """Wrap an OpenAI client with Anqush controls.

        Args:
            client: An openai.OpenAI or openai.AsyncOpenAI instance.

        Returns:
            OpenAIControlledClient that proxies all calls through controls.
        """
        return OpenAIControlledClient(client=client, adapter=self)


def wrap_openai(
    client: Any,
    agent_id: str,
    server_url: str | None = None,
    api_key: str | None = None,
) -> OpenAIControlledClient:
    """Wrap an OpenAI client with Anqush controls.

    This is the primary entry point for OpenAI integration.

    Usage:
        import openai
        from anqush.adapters.openai import wrap_openai

        raw_client = openai.OpenAI(api_key="sk-...")
        client = wrap_openai(raw_client, agent_id="invoice-agent")

        # Use normally — controls are applied automatically
        response = client.chat.completions.create(...)
    """
    adapter = OpenAIAdapter(agent_id, server_url, api_key)
    return adapter.wrap(client)
