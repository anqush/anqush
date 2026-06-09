"""Approval conformance tests.

Verifies that the server correctly implements the approval lifecycle:
- Create approval → poll → resolve
- Response shape matches spec
- Status transitions are correct
"""

from __future__ import annotations

import pytest

from anqush.protocol.transport import Transport
from anqush.protocol.types import (
    ApprovalCreateRequest,
    ApprovalResponse,
    ApprovalStatus,
)


class TestApprovalLifecycle:
    """Test approval create → poll → resolve."""

    def test_create_approval(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Create an approval request."""
        request = ApprovalCreateRequest(
            agent_id=agent_id,
            tool="db.delete",
            params={"table": "users", "id": 123},
            rule={"name": "block-delete", "action": "block"},
        )
        response = transport.create_approval(request)
        assert isinstance(response, ApprovalResponse)
        assert response.id  # non-empty
        assert response.agent_id == agent_id
        assert response.tool == "db.delete"
        assert response.status == ApprovalStatus.PENDING
        assert response.created_at is not None

    def test_get_approval(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Poll an approval request."""
        request = ApprovalCreateRequest(
            agent_id=agent_id,
            tool="send_email",
            params={"to": "test@example.com"},
            rule={"name": "approve-email", "action": "approval"},
        )
        created = transport.create_approval(request)
        polled = transport.get_approval(created.id)
        assert polled.id == created.id
        assert polled.status == ApprovalStatus.PENDING

    def test_approval_response_shape(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Approval response has all required fields."""
        request = ApprovalCreateRequest(
            agent_id=agent_id,
            tool="test_tool",
            params={},
            rule={"name": "test", "action": "approval"},
        )
        response = transport.create_approval(request)
        assert response.id
        assert response.agent_id == agent_id
        assert response.tool == "test_tool"
        assert isinstance(response.params, dict)
        assert isinstance(response.rule, dict)
        assert response.status in ApprovalStatus
        assert response.created_at is not None

    def test_approval_not_found_returns_error(
        self, transport: Transport
    ) -> None:
        """Non-existent approval returns error."""
        with pytest.raises(Exception) as exc_info:
            transport.get_approval("non-existent-approval-xyz")
        error_msg = str(exc_info.value).lower()
        assert "not_found" in error_msg or "404" in error_msg

    def test_approval_with_context(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Approval can include context for the approver."""
        request = ApprovalCreateRequest(
            agent_id=agent_id,
            tool="deploy",
            params={"env": "production"},
            rule={"name": "approve-deploy", "action": "approval"},
            context={"reason": "Deploying hotfix for critical bug"},
        )
        response = transport.create_approval(request)
        assert response.id
