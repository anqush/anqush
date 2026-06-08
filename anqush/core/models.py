"""Shared data types and exceptions for Anqush core.

Protocol types are imported from anqush.protocol.types.
SDK-specific types (exceptions, internal helpers) live here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Re-export protocol types for backward compatibility
from anqush.protocol.types import (
    AuditEvent,
    AuditStatus,
    Rule,
    RuleAction,
)


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


# ─── Internal Types ──────────────────────────────────────────────────────────


@dataclass
class ToolCall:
    """Represents an intercepted tool call (internal to the SDK)."""

    name: str
    params: dict[str, Any]
    agent_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "params": self.params,
            "agent_id": self.agent_id,
        }
