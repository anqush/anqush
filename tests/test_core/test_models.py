"""Tests for anqush.core.models."""

import pytest

from anqush.core.models import (
    ApprovalRequest,
    AuditEvent,
    BudgetExceededError,
    ToolBlockedError,
    ToolCall,
    ToolRejectedError,
)


class TestExceptions:
    """Tests for exception classes."""

    def test_tool_blocked_error(self):
        err = ToolBlockedError(tool="delete_db", reason="Not allowed")
        assert err.tool == "delete_db"
        assert err.reason == "Not allowed"
        assert "delete_db" in str(err)
        assert "Not allowed" in str(err)

    def test_tool_rejected_error(self):
        err = ToolRejectedError(tool="send_email", reason="approval denied")
        assert err.tool == "send_email"
        assert err.reason == "approval denied"

    def test_tool_rejected_error_default_reason(self):
        err = ToolRejectedError(tool="send_email")
        assert err.reason == "approval denied"

    def test_budget_exceeded_error(self):
        err = BudgetExceededError(budget=10.0, current=8.5, requested=2.0)
        assert err.budget == 10.0
        assert err.current == 8.5
        assert err.requested == 2.0
        assert "$10.00" in str(err)
        assert "$8.50" in str(err)
        assert "$2.00" in str(err)


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_creation(self):
        tc = ToolCall(name="search", params={"q": "test"}, agent_id="agent-1")
        assert tc.name == "search"
        assert tc.params == {"q": "test"}
        assert tc.agent_id == "agent-1"

    def test_to_dict(self):
        tc = ToolCall(name="calc", params={"x": 1}, agent_id="a")
        d = tc.to_dict()
        assert d == {"name": "calc", "params": {"x": 1}, "agent_id": "a"}


class TestAuditEvent:
    """Tests for AuditEvent dataclass."""

    def test_creation(self):
        event = AuditEvent(
            agent_id="a",
            tool="search",
            params={"q": "test"},
            status="success",
        )
        assert event.agent_id == "a"
        assert event.status == "success"
        assert event.cost == 0.0

    def test_to_dict(self):
        event = AuditEvent(
            agent_id="a",
            tool="search",
            params={},
            status="blocked",
            reason="blocked by rule",
            cost=0.5,
        )
        d = event.to_dict()
        assert d["status"] == "blocked"
        assert d["reason"] == "blocked by rule"
        assert d["cost"] == 0.5


class TestApprovalRequest:
    """Tests for ApprovalRequest dataclass."""

    def test_creation(self):
        req = ApprovalRequest(
            id="abc-123",
            agent_id="a",
            tool="refund",
            params={"amount": 500},
            rule={"name": "large-refund"},
        )
        assert req.id == "abc-123"
        assert req.status == "pending"

    def test_default_status(self):
        req = ApprovalRequest(
            id="x", agent_id="a", tool="t", params={}, rule={}
        )
        assert req.status == "pending"
