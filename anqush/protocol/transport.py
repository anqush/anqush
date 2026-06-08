"""Abstract Transport interface for the Anqush Protocol.

The transport layer decouples the SDK from the HTTP implementation.
Use HTTPTransport for real servers, LocalTransport for in-process testing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .types import (
    ApprovalCreateRequest,
    ApprovalResponse,
    AuditEvent,
    AuditEventBatch,
    AuditAcceptedResponse,
    BudgetResponse,
    RulesResponse,
)


class Transport(ABC):
    """Abstract interface for talking to an Anqush control plane."""

    @abstractmethod
    def get_rules(self, agent_id: str) -> RulesResponse:
        """Fetch rules for an agent."""
        ...

    @abstractmethod
    def get_budget(self, agent_id: str) -> BudgetResponse:
        """Fetch budget for an agent."""
        ...

    @abstractmethod
    def create_approval(self, request: ApprovalCreateRequest) -> ApprovalResponse:
        """Request human approval for a tool call."""
        ...

    @abstractmethod
    def get_approval(self, approval_id: str) -> ApprovalResponse:
        """Poll approval status."""
        ...

    @abstractmethod
    def submit_audit(self, event: AuditEvent) -> AuditAcceptedResponse:
        """Submit a single audit event."""
        ...

    @abstractmethod
    def submit_audit_batch(self, batch: AuditEventBatch) -> AuditAcceptedResponse:
        """Submit a batch of audit events."""
        ...

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Liveness probe."""
        ...
