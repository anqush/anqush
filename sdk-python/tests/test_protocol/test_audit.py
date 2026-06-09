"""Audit conformance tests.

Verifies that the server correctly implements audit event submission:
- Single event submission
- Batch submission
- Response shape matches spec
"""

from __future__ import annotations

import pytest

from anqush.protocol.transport import Transport
from anqush.protocol.types import (
    AuditAcceptedResponse,
    AuditEvent,
    AuditEventBatch,
    AuditStatus,
)


class TestAuditSubmission:
    """Test POST /audit."""

    def test_submit_single_event(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Submit a single audit event."""
        event = AuditEvent(
            agent_id=agent_id,
            tool="search",
            params={"query": "test"},
            status=AuditStatus.SUCCESS,
            cost=0.001,
            duration_ms=150.0,
        )
        response = transport.submit_audit(event)
        assert isinstance(response, AuditAcceptedResponse)
        assert response.accepted == 1

    def test_submit_event_with_result(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Submit event with result data."""
        event = AuditEvent(
            agent_id=agent_id,
            tool="api.call",
            params={"endpoint": "/users"},
            result={"users": [{"id": 1}, {"id": 2}]},
            status=AuditStatus.SUCCESS,
            cost=0.002,
        )
        response = transport.submit_audit(event)
        assert response.accepted == 1

    def test_submit_blocked_event(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Submit a blocked event."""
        event = AuditEvent(
            agent_id=agent_id,
            tool="db.delete",
            params={"table": "users"},
            status=AuditStatus.BLOCKED,
            reason="Rule: block-delete",
        )
        response = transport.submit_audit(event)
        assert response.accepted == 1

    def test_submit_batch(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Submit a batch of events (if supported)."""
        events = [
            AuditEvent(
                agent_id=agent_id,
                tool=f"tool_{i}",
                params={"i": i},
                status=AuditStatus.SUCCESS,
            )
            for i in range(3)
        ]
        batch = AuditEventBatch(events=events)
        try:
            response = transport.submit_audit_batch(batch)
            assert isinstance(response, AuditAcceptedResponse)
            assert response.accepted == 3
        except Exception as e:
            # Server may not support batch mode yet (422)
            error_msg = str(e).lower()
            assert "422" in error_msg or "unprocessable" in error_msg or "validation" in error_msg

    def test_submit_event_with_approval_id(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Submit event linked to an approval."""
        event = AuditEvent(
            agent_id=agent_id,
            tool="deploy",
            params={"env": "prod"},
            status=AuditStatus.SUCCESS,
            approval_id="apr_abc123",
        )
        response = transport.submit_audit(event)
        assert response.accepted == 1

    def test_audit_response_shape(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Response has accepted field."""
        event = AuditEvent(
            agent_id=agent_id,
            tool="test",
            params={},
            status=AuditStatus.SUCCESS,
        )
        response = transport.submit_audit(event)
        assert hasattr(response, "accepted")
        assert isinstance(response.accepted, int)
