"""Local transport for the Anqush Protocol.

In-process implementation for testing and development. No server required.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .transport import Transport
from .types import (
    ApprovalCreateRequest,
    ApprovalResponse,
    ApprovalStatus,
    AuditAcceptedResponse,
    AuditEvent,
    AuditEventBatch,
    BudgetResponse,
    Rule,
    RulesResponse,
)


class LocalTransport(Transport):
    """In-process transport for testing without a server.

    Stores rules, budget, and approvals in memory. Useful for:
    - Unit tests
    - Local development without running the server
    - Offline mode

    Usage:
        transport = LocalTransport()
        transport.set_rules("my-agent", [
            Rule(id="1", name="block-delete", action="block", tool="db.delete"),
        ])
        rules = transport.get_rules("my-agent")
    """

    def __init__(self) -> None:
        self._rules: dict[str, list[Rule]] = {}
        self._budgets: dict[str, BudgetResponse] = {}
        self._approvals: dict[str, ApprovalResponse] = {}
        self._audit_events: list[AuditEvent] = []

    # ─── Rules ────────────────────────────────────────────────────────────────

    def set_rules(self, agent_id: str, rules: list[Rule], version: str = "1") -> None:
        """Set rules for an agent (test helper)."""
        self._rules[agent_id] = rules

    def get_rules(self, agent_id: str) -> RulesResponse:
        rules = self._rules.get(agent_id, [])
        return RulesResponse(rules=rules, version="1")

    # ─── Budget ───────────────────────────────────────────────────────────────

    def set_budget(self, budget: BudgetResponse) -> None:
        """Set budget for an agent (test helper)."""
        self._budgets[budget.agent_id] = budget

    def get_budget(self, agent_id: str) -> BudgetResponse:
        return self._budgets.get(
            agent_id,
            BudgetResponse(agent_id=agent_id),
        )

    # ─── Approvals ────────────────────────────────────────────────────────────

    def create_approval(self, request: ApprovalCreateRequest) -> ApprovalResponse:
        approval_id = f"apr_{uuid.uuid4().hex[:8]}"
        response = ApprovalResponse(
            id=approval_id,
            agent_id=request.agent_id,
            tool=request.tool,
            params=request.params,
            rule=request.rule,
            status=ApprovalStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        self._approvals[approval_id] = response
        return response

    def get_approval(self, approval_id: str) -> ApprovalResponse:
        approval = self._approvals.get(approval_id)
        if not approval:
            raise Exception(f"Approval {approval_id} not found")
        return approval

    def resolve_approval(
        self,
        approval_id: str,
        status: ApprovalStatus,
        resolved_by: str | None = None,
        comment: str | None = None,
    ) -> ApprovalResponse:
        """Resolve an approval (test helper)."""
        approval = self._approvals.get(approval_id)
        if not approval:
            raise Exception(f"Approval {approval_id} not found")
        # Create new response with resolved status
        resolved = approval.model_copy(
            update={
                "status": status,
                "resolved_at": datetime.now(timezone.utc),
                "resolved_by": resolved_by,
                "comment": comment,
            }
        )
        self._approvals[approval_id] = resolved
        return resolved

    # ─── Audit ────────────────────────────────────────────────────────────────

    def submit_audit(self, event: AuditEvent) -> AuditAcceptedResponse:
        self._audit_events.append(event)
        return AuditAcceptedResponse(accepted=1)

    def submit_audit_batch(self, batch: AuditEventBatch) -> AuditAcceptedResponse:
        self._audit_events.extend(batch.events)
        return AuditAcceptedResponse(accepted=len(batch.events))

    def get_audit_events(self, agent_id: str | None = None) -> list[AuditEvent]:
        """Get audit events (test helper)."""
        if agent_id:
            return [e for e in self._audit_events if e.agent_id == agent_id]
        return list(self._audit_events)

    # ─── Health ───────────────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        return {"status": "ok"}
