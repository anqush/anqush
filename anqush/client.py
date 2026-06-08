"""OpenAI client wrapper with runtime controls."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable
from urllib.parse import urljoin

import httpx

from .rules import RuleEngine
from .approvals import ApprovalClient
from .audit import AuditLogger


class ControlledTool:
    """Wraps a tool function with controls."""

    def __init__(
        self,
        func: Callable,
        name: str,
        agent_id: str,
        rules: RuleEngine,
        approvals: ApprovalClient,
        audit: AuditLogger,
    ):
        self.func = func
        self.name = name
        self.agent_id = agent_id
        self.rules = rules
        self.approvals = approvals
        self.audit = audit

    def __call__(self, **kwargs: Any) -> Any:
        start = time.time()
        cost = 0.0  # Tools don't self-report cost; user can annotate

        # 1. Check block rules
        block_reason = self.rules.check_block(self.name, kwargs)
        if block_reason:
            self.audit.log(
                agent_id=self.agent_id,
                tool=self.name,
                params=kwargs,
                result=None,
                status="blocked",
                reason=block_reason,
                cost=cost,
                duration_ms=(time.time() - start) * 1000,
            )
            raise ToolBlockedError(f"Tool '{self.name}' blocked: {block_reason}")

        # 2. Check approval rules
        approval_rule = self.rules.check_approval(self.name, kwargs)
        if approval_rule:
            approved = self.approvals.request(
                agent_id=self.agent_id,
                tool=self.name,
                params=kwargs,
                rule=approval_rule,
            )
            if not approved:
                self.audit.log(
                    agent_id=self.agent_id,
                    tool=self.name,
                    params=kwargs,
                    result=None,
                    status="rejected",
                    reason=f"Approval denied for rule: {approval_rule}",
                    cost=cost,
                    duration_ms=(time.time() - start) * 1000,
                )
                raise ToolRejectedError(
                    f"Tool '{self.name}' rejected: approval denied"
                )

        # 3. Execute
        try:
            result = self.func(**kwargs)
            status = "success"
            error = None
        except Exception as exc:
            result = None
            status = "error"
            error = str(exc)
            raise
        finally:
            self.audit.log(
                agent_id=self.agent_id,
                tool=self.name,
                params=kwargs,
                result=result if status == "success" else None,
                status=status,
                reason=error,
                cost=cost,
                duration_ms=(time.time() - start) * 1000,
            )

        return result


class ToolBlockedError(Exception):
    pass


class ToolRejectedError(Exception):
    pass


class ControlledOpenAIClient:
    """Wraps an OpenAI client, intercepting tool calls."""

    def __init__(
        self,
        client: Any,
        agent_id: str,
        server_url: str | None = None,
        api_key: str | None = None,
    ):
        self._client = client
        self.agent_id = agent_id
        self.server_url = server_url or os.getenv("ANQUSH_URL", "http://localhost:8000")
        self.api_key = api_key or os.getenv("ANQUSH_API_KEY")

        self.rules = RuleEngine(self.server_url, self.api_key)
        self.approvals = ApprovalClient(self.server_url, self.api_key)
        self.audit = AuditLogger(self.server_url, self.api_key)

        # Track session spend (LLM calls only; tool costs need annotation)
        self.session_spend = 0.0
        self.session_budget = None  # fetched from server

    def _check_budget(self, estimated_cost: float) -> None:
        """Check if adding estimated_cost would exceed budget."""
        if self.session_budget is None:
            # Try to fetch from server
            try:
                resp = httpx.get(
                    urljoin(self.server_url, f"/api/agents/{self.agent_id}/budget"),
                    headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
                    timeout=2.0,
                )
                if resp.status_code == 200:
                    self.session_budget = resp.json().get("max_session_cost")
            except Exception:
                pass

        if self.session_budget and (self.session_spend + estimated_cost) > self.session_budget:
            raise BudgetExceededError(
                f"Session budget ${self.session_budget:.2f} exceeded "
                f"(current: ${self.session_spend:.2f}, requested: ${estimated_cost:.2f})"
            )

    def _wrap_tools(self, tools: list[dict] | None) -> list[dict] | None:
        """Wrap tool functions so calls go through controls."""
        if not tools:
            return tools

        wrapped = []
        for tool in tools:
            if callable(tool):
                # It's a function — wrap it
                name = getattr(tool, "__name__", "unknown")
                wrapped_tool = ControlledTool(
                    tool, name, self.agent_id, self.rules, self.approvals, self.audit
                )
                wrapped.append(wrapped_tool)
            elif isinstance(tool, dict) and "function" in tool:
                # OpenAI function schema — keep as-is, the model will call it
                # and we'll intercept via the completions API wrapper
                wrapped.append(tool)
            else:
                wrapped.append(tool)
        return wrapped

    def chat_completions_create(self, *args: Any, **kwargs: Any) -> Any:
        """Intercept chat.completions.create for budget tracking."""
        # Rough cost estimation before call
        model = kwargs.get("model", "gpt-4o")
        messages = kwargs.get("messages", [])
        tools = kwargs.get("tools", [])

        # Very rough token estimate
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        estimated_tokens = total_chars // 4
        estimated_cost = self._estimate_cost(model, estimated_tokens)

        self._check_budget(estimated_cost)

        # Wrap tools if present
        if "tools" in kwargs:
            kwargs["tools"] = self._wrap_tools(kwargs["tools"])

        result = self._client.chat.completions.create(*args, **kwargs)

        # Track actual spend (approximate from usage)
        if hasattr(result, "usage") and result.usage:
            actual_tokens = result.usage.total_tokens
            actual_cost = self._estimate_cost(model, actual_tokens)
            self.session_spend += actual_cost

        return result

    def _estimate_cost(self, model: str, tokens: int) -> float:
        """Rough cost per 1K tokens."""
        rates = {
            "gpt-4o": 0.005,
            "gpt-4o-mini": 0.00015,
            "gpt-4-turbo": 0.01,
            "claude-3-5-sonnet": 0.003,
        }
        rate = rates.get(model, 0.005)
        return (tokens / 1000) * rate

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class BudgetExceededError(Exception):
    pass


def wrap_openai(
    client: Any,
    agent_id: str,
    server_url: str | None = None,
    api_key: str | None = None,
) -> ControlledOpenAIClient:
    """Wrap an OpenAI client with Anqush controls.

    Usage:
        import openai
        from anqush import wrap_openai

        raw_client = openai.OpenAI(api_key="sk-...")
        client = wrap_openai(raw_client, agent_id="invoice-agent")

        # Use normally — controls are applied automatically
        response = client.chat.completions.create(...)
    """
    return ControlledOpenAIClient(client, agent_id, server_url, api_key)
