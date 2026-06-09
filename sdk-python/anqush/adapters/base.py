"""Base adapter — shared control flow for all frameworks."""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from typing import Any

from ..core.rules import RuleEngine
from ..core.approvals import ApprovalClient
from ..core.audit import AuditLogger
from ..core.budget import BudgetTracker
from ..core.models import ToolBlockedError, ToolRejectedError


class ControlledTool:
    """Wraps a tool function with Anqush controls.

    This is the core control flow used by all adapters:
    1. Check block rules
    2. Check approval rules
    3. Execute the tool
    4. Log audit event
    """

    def __init__(
        self,
        func: Any,
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
        cost = 0.0

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
            raise ToolBlockedError(tool=self.name, reason=block_reason)

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
                raise ToolRejectedError(tool=self.name, reason="approval denied")

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


class AgentAdapter(ABC):
    """Base class for framework adapters.

    Provides shared initialization and control utilities.
    Subclasses implement framework-specific wrapping.
    """

    def __init__(
        self,
        agent_id: str,
        server_url: str | None = None,
        api_key: str | None = None,
    ):
        self.agent_id = agent_id
        self.server_url = server_url or os.getenv("ANQUSH_URL", "http://localhost:8000")
        self.api_key = api_key or os.getenv("ANQUSH_API_KEY")

        # Core services
        self.rules = RuleEngine(self.server_url, self.api_key)
        self.approvals = ApprovalClient(self.server_url, self.api_key)
        self.audit = AuditLogger(self.server_url, self.api_key)
        self.budget = BudgetTracker(self.server_url, self.api_key)

        # Fetch budget from server
        self.budget.fetch_budget_for_agent(agent_id)

    def controlled_tool(self, func: Any, name: str | None = None) -> ControlledTool:
        """Create a ControlledTool that wraps a function with controls."""
        return ControlledTool(
            func=func,
            name=name or getattr(func, "__name__", "unknown"),
            agent_id=self.agent_id,
            rules=self.rules,
            approvals=self.approvals,
            audit=self.audit,
        )

    @abstractmethod
    def wrap(self, client_or_context: Any, **kwargs: Any) -> Any:
        """Wrap a client or context with Anqush controls.

        Each adapter implements this to intercept tool calls
        in its framework's idiomatic way.
        """
        ...
