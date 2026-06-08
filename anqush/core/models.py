"""Shared data types and exceptions for Anqush core."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ─── Exceptions ───────────────────────────────────────────────────────────────


class ToolBlockedError(Exception):
    """Raised when a tool call is blocked by a rule."""

    def __init__(self, tool: str, reason: str):
        self.tool = tool
        self.reason = reason
        super().__init__(f"Tool '{tool}' blocked: {reason}")


class ToolRejectedError(Exception):
    """Raised when a tool call is rejected (approval denied or timed out)."""

    def __init__(self, tool: str, reason: str = "approval denied"):
        self.tool = tool
        self.reason = reason
        super().__init__(f"Tool '{tool}' rejected: {reason}")


class BudgetExceededError(Exception):
    """Raised when a tool call would exceed the budget limit."""

    def __init__(self, budget: float, current: float, requested: float):
        self.budget = budget
        self.current = current
        self.requested = requested
        super().__init__(
            f"Budget ${budget:.2f} exceeded (current: ${current:.2f}, requested: ${requested:.2f})"
        )


# ─── Data Types ───────────────────────────────────────────────────────────────


@dataclass
class ToolCall:
    """Represents an intercepted tool call."""

    name: str
    params: dict[str, Any]
    agent_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "params": self.params,
            "agent_id": self.agent_id,
        }


@dataclass
class AuditEvent:
    """An audit log entry for a tool call."""

    agent_id: str
    tool: str
    params: dict[str, Any]
    status: str  # "success" | "blocked" | "rejected" | "error"
    result: Any = None
    reason: str | None = None
    cost: float = 0.0
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "tool": self.tool,
            "params": self.params,
            "status": self.status,
            "result": self.result,
            "reason": self.reason,
            "cost": self.cost,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ApprovalRequest:
    """A pending approval request."""

    id: str
    agent_id: str
    tool: str
    params: dict[str, Any]
    rule: dict[str, Any]
    status: str = "pending"  # "pending" | "approved" | "rejected"
