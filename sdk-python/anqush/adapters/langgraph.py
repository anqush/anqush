"""LangGraph adapter — intercepts tool calls at the ToolNode level.

Uses LangGraph's `wrap_tool_call` parameter to intercept tool execution
and `interrupt()` for human-in-the-loop approvals.
"""

from __future__ import annotations

import time
from typing import Any, Callable
from urllib.parse import urljoin

import httpx
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from .base import AgentAdapter, ControlledTool
from ..core.models import ToolBlockedError, ToolRejectedError


class ControlledToolNode:
    """Wraps a LangGraph ToolNode with Anqush controls.

    Intercepts every tool call to:
    1. Check block rules
    2. Check approval rules (uses interrupt() for human-in-the-loop)
    3. Execute the tool
    4. Log audit event
    """

    def __init__(
        self,
        tools: list[Any],
        adapter: AgentAdapter,
        name: str = "tools",
        **tool_node_kwargs: Any,
    ):
        self._adapter = adapter
        self._tool_names = [getattr(t, "name", getattr(t, "__name__", "unknown")) for t in tools]

        # Create the underlying ToolNode with our interceptor
        self._node = ToolNode(
            tools=tools,
            name=name,
            wrap_tool_call=self._make_wrapper(),
            **tool_node_kwargs,
        )

    def _make_wrapper(self) -> Callable:
        """Create a wrap_tool_call function that applies Anqush controls."""
        adapter = self._adapter

        def wrapper(request, execute):
            tool_name = request.tool_call.get("name", "unknown")
            tool_args = request.tool_call.get("args", {})
            agent_id = adapter.agent_id

            start = time.time()

            # 1. Check block rules
            block_reason = adapter.rules.check_block(tool_name, tool_args)
            if block_reason:
                adapter.audit.log(
                    agent_id=agent_id,
                    tool=tool_name,
                    params=tool_args,
                    result=None,
                    status="blocked",
                    reason=block_reason,
                    cost=0.0,
                    duration_ms=(time.time() - start) * 1000,
                )
                return ToolMessage(
                    content=f"Blocked by Anqush: {block_reason}",
                    tool_call_id=request.tool_call.get("id", ""),
                    status="error",
                )

            # 2. Check approval rules
            approval_rule = adapter.rules.check_approval(tool_name, tool_args)
            if approval_rule:
                # Use interrupt() to pause for human approval
                approval_decision = interrupt(
                    {
                        "type": "approval_required",
                        "tool": tool_name,
                        "args": tool_args,
                        "rule": approval_rule,
                        "agent_id": agent_id,
                    }
                )

                # Check the approval decision
                if not approval_decision or approval_decision.get("approved") is not True:
                    adapter.audit.log(
                        agent_id=agent_id,
                        tool=tool_name,
                        params=tool_args,
                        result=None,
                        status="rejected",
                        reason=f"Approval denied for rule: {approval_rule}",
                        cost=0.0,
                        duration_ms=(time.time() - start) * 1000,
                    )
                    return ToolMessage(
                        content=f"Rejected by Anqush: approval denied",
                        tool_call_id=request.tool_call.get("id", ""),
                        status="error",
                    )

            # 3. Execute the tool
            try:
                result = execute(request)
                status = "success"
                error = None
            except Exception as exc:
                result = ToolMessage(
                    content=f"Tool error: {exc}",
                    tool_call_id=request.tool_call.get("id", ""),
                    status="error",
                )
                status = "error"
                error = str(exc)
                raise
            finally:
                adapter.audit.log(
                    agent_id=agent_id,
                    tool=tool_name,
                    params=tool_args,
                    result=str(result) if status == "success" else None,
                    status=status,
                    reason=error,
                    cost=0.0,
                    duration_ms=(time.time() - start) * 1000,
                )

            return result

        return wrapper

    def invoke(self, state: Any, config: Any = None, **kwargs: Any) -> Any:
        """Invoke the controlled tool node."""
        if config:
            return self._node.invoke(state, config, **kwargs)
        return self._node.invoke(state, **kwargs)

    async def ainvoke(self, state: Any, config: Any = None, **kwargs: Any) -> Any:
        """Async invoke the controlled tool node."""
        if config:
            return await self._node.ainvoke(state, config, **kwargs)
        return await self._node.ainvoke(state, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """Proxy all other attributes to the underlying ToolNode."""
        return getattr(self._node, name)


class LangGraphAdapter(AgentAdapter):
    """Adapter for LangGraph agents.

    Wraps ToolNode instances to intercept tool calls and enforce controls.
    """

    def wrap_tool_node(
        self,
        tools: list[Any],
        name: str = "tools",
        **tool_node_kwargs: Any,
    ) -> ControlledToolNode:
        """Wrap LangGraph tools with Anqush controls.

        Args:
            tools: List of tools (BaseTool instances or callables).
            name: Name for the ToolNode.
            **tool_node_kwargs: Additional kwargs passed to ToolNode.

        Returns:
            ControlledToolNode that applies controls to all tool calls.
        """
        return ControlledToolNode(
            tools=tools,
            adapter=self,
            name=name,
            **tool_node_kwargs,
        )

    def wrap(self, client_or_context: Any, **kwargs: Any) -> Any:
        """Wrap a LangGraph context with controls.

        For LangGraph, use wrap_tool_node() instead for more control.
        This method is provided for interface compatibility.
        """
        raise NotImplementedError(
            "Use wrap_tool_node() for LangGraph integration. "
            "It provides more control over tool node wrapping."
        )


def wrap_tool_node(
    tools: list[Any],
    agent_id: str,
    server_url: str | None = None,
    api_key: str | None = None,
    name: str = "tools",
    **tool_node_kwargs: Any,
) -> ControlledToolNode:
    """Wrap LangGraph tools with Anqush controls.

    This is the primary entry point for LangGraph integration.

    Usage:
        from langgraph.prebuilt import create_react_agent
        from anqush.adapters.langgraph import wrap_tool_node

        tools = [search, calculator, send_email]
        controlled_tools = wrap_tool_node(tools, agent_id="research-agent")

        # Use in a LangGraph agent
        graph = create_react_agent(model, controlled_tools)
    """
    adapter = LangGraphAdapter(agent_id, server_url, api_key)
    return adapter.wrap_tool_node(tools, name=name, **tool_node_kwargs)
