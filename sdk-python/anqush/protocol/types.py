"""Pydantic models for the Anqush Protocol.

These models mirror the schemas in docs/protocol/openapi.yaml. The server
and SDK both import from here to stay in sync with the spec.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── Enums ────────────────────────────────────────────────────────────────────


class RuleAction(str, Enum):
    """What happens when a rule matches."""

    BLOCK = "block"
    APPROVAL = "approval"


class ApprovalStatus(str, Enum):
    """Lifecycle states of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class AuditStatus(str, Enum):
    """Outcome of a tool call."""

    SUCCESS = "success"
    BLOCKED = "blocked"
    REJECTED = "rejected"
    ERROR = "error"


class ErrorCode(str, Enum):
    """Machine-readable error codes. Stable across server versions."""

    INVALID_REQUEST = "invalid_request"
    INVALID_RULE = "invalid_rule"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    AGENT_NOT_FOUND = "agent_not_found"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    BATCH_TOO_LARGE = "batch_too_large"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"
    UNAVAILABLE = "unavailable"


# ─── Rules ────────────────────────────────────────────────────────────────────


class Rule(BaseModel):
    """A runtime rule evaluated by the SDK against tool calls."""

    id: str
    name: str
    action: RuleAction
    tool: str = "*"
    when: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None


class RulesResponse(BaseModel):
    """Response from GET /agents/{agent_id}/rules."""

    rules: list[Rule]
    version: str


# ─── Budget ───────────────────────────────────────────────────────────────────


class BudgetResponse(BaseModel):
    """Response from GET /agents/{agent_id}/budget."""

    agent_id: str
    max_session_cost: float | None = None
    max_daily_cost: float | None = None
    session_spend: float = 0.0
    daily_spend: float = 0.0
    currency: str = "USD"


# ─── Approvals ────────────────────────────────────────────────────────────────


class ApprovalCreateRequest(BaseModel):
    """Request body for POST /approvals."""

    agent_id: str
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)
    rule: dict[str, Any] = Field(default_factory=dict)
    callback_url: str | None = None
    timeout_seconds: float = 300.0
    context: dict[str, Any] | None = None


class ApprovalResolveRequest(BaseModel):
    """Request body for POST /approvals/{id}/resolve."""

    status: Literal["approved", "rejected"]
    resolved_by: str | None = None
    comment: str | None = None


class ApprovalResponse(BaseModel):
    """Response from POST /approvals and GET /approvals/{id}."""

    id: str
    agent_id: str
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)
    rule: dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus
    created_at: datetime
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    comment: str | None = None
    resume_url: str | None = None


# ─── Audit ────────────────────────────────────────────────────────────────────


class AuditEvent(BaseModel):
    """A single audit event for a tool call."""

    kind: Literal["single"] = "single"
    agent_id: str
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    status: AuditStatus
    reason: str | None = None
    cost: float = 0.0
    duration_ms: float = 0.0
    occurred_at: datetime | None = None
    approval_id: str | None = None


class AuditEventBatch(BaseModel):
    """Batch of audit events (max 100)."""

    kind: Literal["batch"] = "batch"
    events: list[AuditEvent]


class AuditAcceptedResponse(BaseModel):
    """Response from POST /audit."""

    accepted: int


# ─── Errors ───────────────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    """Error response from any failing endpoint."""

    code: ErrorCode
    message: str
    request_id: str


