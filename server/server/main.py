"""Anqush Control Plane — FastAPI server (reference implementation).

Implements the Anqush Protocol spec (docs/protocol/openapi.yaml).
Single-tenant, SQLite-backed, for dev and self-hosting.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from anqush.protocol.types import (
    ApprovalCreateRequest,
    ApprovalResponse,
    ApprovalResolveRequest,
    ApprovalStatus,
    AuditAcceptedResponse,
    AuditEvent,
    AuditEventBatch,
    BudgetResponse,
    ErrorCode,
    ErrorResponse,
    Rule,
    RulesResponse,
)

from .db import Database

db = Database()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    yield
    db.close()


app = FastAPI(
    title="Anqush",
    version="0.1.0",
    description="Reference implementation of the Anqush Protocol",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Error handling ──────────────────────────────────────────────────────────


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Convert HTTPExceptions to protocol-compliant error responses."""
    code_map = {
        400: ErrorCode.INVALID_REQUEST,
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        409: ErrorCode.CONFLICT,
        422: ErrorCode.INVALID_REQUEST,
        429: ErrorCode.RATE_LIMITED,
        500: ErrorCode.INTERNAL_ERROR,
    }
    code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    error = ErrorResponse(
        code=code,
        message=str(exc.detail),
        request_id=f"req_{uuid.uuid4().hex[:8]}",
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error.model_dump(),
    )


# ─── Health ──────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0", "service": "anqush-server"}


# ─── Rules (protocol endpoints) ─────────────────────────────────────────────


@app.get("/api/agents/{agent_id}/rules")
def get_rules(agent_id: str) -> RulesResponse:
    """Fetch rules for an agent."""
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")

    rules_data = db.list_rules(agent_id)
    rules = [
        Rule(
            id=str(r["id"]),
            name=r["name"],
            action=r["action"],
            tool=r["tool"],
            when=r.get("when", {}),
            reason=r.get("reason"),
        )
        for r in rules_data
    ]
    return RulesResponse(rules=rules, version="1")


# ─── Budget (protocol endpoint) ─────────────────────────────────────────────


@app.get("/api/agents/{agent_id}/budget")
def get_budget(agent_id: str) -> BudgetResponse:
    """Fetch budget for an agent."""
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")

    budget = db.get_budget(agent_id)
    return BudgetResponse(
        agent_id=budget["agent_id"],
        max_session_cost=budget.get("max_session_cost"),
        max_daily_cost=budget.get("max_daily_cost"),
        session_spend=budget.get("session_spend", 0.0),
        daily_spend=budget.get("daily_spend", 0.0),
        currency="USD",
    )


# ─── Approvals (protocol endpoints) ─────────────────────────────────────────


@app.post("/api/approvals", status_code=201)
def create_approval(request: ApprovalCreateRequest) -> ApprovalResponse:
    """Create an approval request."""
    # Verify agent exists
    agent = db.get_agent(request.agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{request.agent_id}' not found")

    # Create approval
    approval_id = f"apr_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    # Store in DB
    db.create_approval_raw(
        id=approval_id,
        agent_id=request.agent_id,
        tool=request.tool,
        params=request.params,
        rule=request.rule,
    )

    return ApprovalResponse(
        id=approval_id,
        agent_id=request.agent_id,
        tool=request.tool,
        params=request.params,
        rule=request.rule,
        status=ApprovalStatus.PENDING,
        created_at=now,
    )


@app.get("/api/approvals/{approval_id}")
def get_approval(approval_id: str) -> ApprovalResponse:
    """Poll approval status."""
    approval = db.get_approval(approval_id)
    if not approval:
        raise HTTPException(404, f"Approval '{approval_id}' not found")

    return ApprovalResponse(
        id=approval["id"],
        agent_id=approval["agent_id"],
        tool=approval["tool"],
        params=approval.get("params", {}),
        rule=approval.get("rule", {}),
        status=approval["status"],
        created_at=approval["created_at"],
        resolved_at=approval.get("resolved_at"),
        resolved_by=approval.get("resolved_by"),
        comment=approval.get("comment"),
    )


@app.post("/api/approvals/{approval_id}/resolve")
def resolve_approval(
    approval_id: str, request: ApprovalResolveRequest
) -> ApprovalResponse:
    """Resolve an approval request."""
    approval = db.get_approval(approval_id)
    if not approval:
        raise HTTPException(404, f"Approval '{approval_id}' not found")

    if approval["status"] != "pending":
        raise HTTPException(409, "Approval already resolved")

    # Resolve
    db.resolve_approval(
        approval_id,
        status=request.status,
        resolved_by=request.resolved_by,
        comment=request.comment,
    )

    # Return updated approval
    updated = db.get_approval(approval_id)
    return ApprovalResponse(
        id=updated["id"],
        agent_id=updated["agent_id"],
        tool=updated["tool"],
        params=updated.get("params", {}),
        rule=updated.get("rule", {}),
        status=updated["status"],
        created_at=updated["created_at"],
        resolved_at=updated.get("resolved_at"),
        resolved_by=updated.get("resolved_by"),
        comment=updated.get("comment"),
    )


@app.post("/api/approvals/{approval_id}/approve")
def approve(approval_id: str):
    """Legacy: approve an approval (use /resolve instead)."""
    approval = db.get_approval(approval_id)
    if not approval:
        raise HTTPException(404, f"Approval '{approval_id}' not found")

    db.resolve_approval(approval_id, status="approved")
    return {"ok": True}


@app.post("/api/approvals/{approval_id}/reject")
def reject(approval_id: str):
    """Legacy: reject an approval (use /resolve instead)."""
    approval = db.get_approval(approval_id)
    if not approval:
        raise HTTPException(404, f"Approval '{approval_id}' not found")

    db.resolve_approval(approval_id, status="rejected")
    return {"ok": True}


@app.get("/api/approvals")
def list_approvals(agent_id: str | None = None, status: str | None = None):
    """List approvals (internal/admin endpoint)."""
    return db.list_approvals(agent_id, status)


# ─── Audit (protocol endpoint) ──────────────────────────────────────────────


@app.post("/api/audit", status_code=202)
def submit_audit(request: Request):
    """Submit audit event(s)."""
    # Parse body
    import asyncio

    body = asyncio.run(request.json())

    # Handle single vs batch
    kind = body.get("kind", "single")

    if kind == "batch":
        events = body.get("events", [])
        if len(events) > 100:
            raise HTTPException(413, "Batch too large (max 100)")

        for event_data in events:
            db.log_audit_raw(
                agent_id=event_data["agent_id"],
                tool=event_data["tool"],
                params=event_data.get("params", {}),
                result=event_data.get("result"),
                status=event_data["status"],
                reason=event_data.get("reason"),
                cost=event_data.get("cost", 0.0),
                duration_ms=event_data.get("duration_ms", 0.0),
            )

        return AuditAcceptedResponse(accepted=len(events))
    else:
        # Single event
        db.log_audit_raw(
            agent_id=body["agent_id"],
            tool=body["tool"],
            params=body.get("params", {}),
            result=body.get("result"),
            status=body["status"],
            reason=body.get("reason"),
            cost=body.get("cost", 0.0),
            duration_ms=body.get("duration_ms", 0.0),
        )
        return AuditAcceptedResponse(accepted=1)


@app.get("/api/audit")
def list_audit(agent_id: str | None = None, limit: int = 100):
    """List audit events (internal/admin endpoint)."""
    return db.list_audit(agent_id, limit)


# ─── Agents (internal/admin endpoints, not in protocol spec) ────────────────


@app.post("/api/agents")
def create_agent(agent: dict):
    """Create an agent (admin endpoint, not in protocol spec)."""
    return db.create_agent_raw(
        id=agent["id"],
        name=agent["name"],
        max_session_cost=agent.get("max_session_cost"),
        max_daily_cost=agent.get("max_daily_cost"),
    )


@app.get("/api/agents")
def list_agents():
    """List agents (admin endpoint)."""
    return db.list_agents()


@app.get("/api/agents/{agent_id}")
def get_agent(agent_id: str):
    """Get agent details (admin endpoint)."""
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    return agent


@app.post("/api/agents/{agent_id}/spend")
def record_spend(agent_id: str, amount: float):
    """Record spend (admin endpoint)."""
    db.record_spend(agent_id, amount)
    return {"ok": True}


@app.post("/api/agents/{agent_id}/rules")
def create_rule(agent_id: str, rule: dict):
    """Create a rule (admin endpoint)."""
    # Verify agent exists
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")

    return db.create_rule_raw(
        agent_id=agent_id,
        name=rule["name"],
        action=rule["action"],
        tool=rule.get("tool", "*"),
        when=rule.get("when", {}),
        reason=rule.get("reason"),
    )


@app.delete("/api/agents/{agent_id}/rules/{rule_id}")
def delete_rule(agent_id: str, rule_id: int):
    """Delete a rule (admin endpoint)."""
    db.delete_rule(rule_id)
    return {"ok": True}
