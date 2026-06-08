"""Anqush Control Plane — FastAPI server."""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Body, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .db import Database


db = Database()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    yield
    db.close()


app = FastAPI(title="Anqush", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Models ───────────────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    id: str
    name: str
    max_session_cost: float | None = None
    max_daily_cost: float | None = None


class AgentOut(BaseModel):
    id: str
    name: str
    max_session_cost: float | None = None
    max_daily_cost: float | None = None
    created_at: datetime


class RuleCreate(BaseModel):
    name: str
    action: str  # "block" | "approval"
    tool: str = "*"
    when: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None


class RuleOut(RuleCreate):
    id: int
    agent_id: str
    created_at: datetime


class ApprovalCreate(BaseModel):
    agent_id: str
    tool: str
    params: dict[str, Any]
    rule: dict[str, Any]


class ApprovalOut(BaseModel):
    id: str
    agent_id: str
    tool: str
    params: dict[str, Any]
    rule: dict[str, Any]
    status: str  # "pending" | "approved" | "rejected"
    created_at: datetime
    resolved_at: datetime | None = None


class AuditEvent(BaseModel):
    agent_id: str
    tool: str
    params: dict[str, Any]
    result: Any | None = None
    status: str
    reason: str | None = None
    cost: float = 0.0
    duration_ms: float = 0.0


class BudgetOut(BaseModel):
    agent_id: str
    max_session_cost: float | None = None
    max_daily_cost: float | None = None
    session_spend: float = 0.0
    daily_spend: float = 0.0


# ─── Agents ───────────────────────────────────────────────────────────────────

@app.post("/api/agents", response_model=AgentOut)
def create_agent(agent: AgentCreate):
    return db.create_agent(agent)


@app.get("/api/agents", response_model=list[AgentOut])
def list_agents():
    return db.list_agents()


@app.get("/api/agents/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: str):
    a = db.get_agent(agent_id)
    if not a:
        raise HTTPException(404, "Agent not found")
    return a


@app.get("/api/agents/{agent_id}/budget", response_model=BudgetOut)
def get_budget(agent_id: str):
    return db.get_budget(agent_id)


@app.post("/api/agents/{agent_id}/spend")
def record_spend(agent_id: str, amount: float = Body(..., embed=True)):
    db.record_spend(agent_id, amount)
    return {"ok": True}


# ─── Rules ────────────────────────────────────────────────────────────────────

@app.post("/api/agents/{agent_id}/rules", response_model=RuleOut)
def create_rule(agent_id: str, rule: RuleCreate):
    return db.create_rule(agent_id, rule)


@app.get("/api/agents/{agent_id}/rules", response_model=list[RuleOut])
def list_rules(agent_id: str):
    return db.list_rules(agent_id)


@app.delete("/api/agents/{agent_id}/rules/{rule_id}")
def delete_rule(agent_id: str, rule_id: int):
    db.delete_rule(rule_id)
    return {"ok": True}


# ─── Approvals ────────────────────────────────────────────────────────────────

@app.post("/api/approvals", response_model=ApprovalOut)
def create_approval(req: ApprovalCreate):
    return db.create_approval(req)


@app.get("/api/approvals/{approval_id}", response_model=ApprovalOut)
def get_approval(approval_id: str):
    a = db.get_approval(approval_id)
    if not a:
        raise HTTPException(404, "Approval not found")
    return a


@app.post("/api/approvals/{approval_id}/approve")
def approve(approval_id: str):
    a = db.resolve_approval(approval_id, "approved")
    if not a:
        raise HTTPException(404, "Approval not found")
    return a


@app.post("/api/approvals/{approval_id}/reject")
def reject(approval_id: str):
    a = db.resolve_approval(approval_id, "rejected")
    if not a:
        raise HTTPException(404, "Approval not found")
    return a


@app.get("/api/approvals", response_model=list[ApprovalOut])
def list_approvals(agent_id: str | None = None, status: str | None = None):
    return db.list_approvals(agent_id, status)


# ─── Audit ────────────────────────────────────────────────────────────────────

@app.post("/api/audit")
def log_audit(event: AuditEvent):
    db.log_audit(event)
    return {"ok": True}


@app.get("/api/audit")
def list_audit(agent_id: str | None = None, limit: int = 100):
    return db.list_audit(agent_id, limit)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}
