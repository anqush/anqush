"""Tests for server.main API endpoints."""

import pytest
from fastapi.testclient import TestClient

from server.main import app


@pytest.fixture
def client(tmp_db):
    """Create a test client with a temporary database."""
    import server.main as server_module
    from server.db import Database

    # Override the database path
    server_module.db = Database(tmp_db)
    server_module.db.init()

    with TestClient(app) as c:
        yield c

    server_module.db.close()


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestAgentEndpoints:
    """Tests for /api/agents endpoints."""

    def test_create_agent(self, client):
        response = client.post(
            "/api/agents",
            json={"id": "test-agent", "name": "Test Agent"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-agent"
        assert data["name"] == "Test Agent"

    def test_list_agents(self, client):
        # Create an agent first
        client.post(
            "/api/agents",
            json={"id": "agent-1", "name": "Agent 1"},
        )

        response = client.get("/api/agents")
        assert response.status_code == 200
        agents = response.json()
        assert len(agents) >= 1

    def test_get_agent(self, client):
        client.post(
            "/api/agents",
            json={"id": "agent-1", "name": "Agent 1"},
        )

        response = client.get("/api/agents/agent-1")
        assert response.status_code == 200
        assert response.json()["id"] == "agent-1"

    def test_get_agent_not_found(self, client):
        response = client.get("/api/agents/nonexistent")
        assert response.status_code == 404

    def test_get_budget(self, client):
        client.post(
            "/api/agents",
            json={
                "id": "agent-1",
                "name": "Agent 1",
                "max_session_cost": 10.0,
                "max_daily_cost": 50.0,
            },
        )

        response = client.get("/api/agents/agent-1/budget")
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "agent-1"
        assert data["max_session_cost"] == 10.0

    def test_record_spend(self, client):
        client.post(
            "/api/agents",
            json={"id": "agent-1", "name": "Agent 1"},
        )

        response = client.post(
            "/api/agents/agent-1/spend",
            json={"amount": 5.0},
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True


class TestRuleEndpoints:
    """Tests for /api/agents/{id}/rules endpoints."""

    def test_create_rule(self, client):
        client.post(
            "/api/agents",
            json={"id": "agent-1", "name": "Agent 1"},
        )

        response = client.post(
            "/api/agents/agent-1/rules",
            json={
                "name": "block-delete",
                "action": "block",
                "tool": "delete_file",
                "reason": "Not allowed",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "block-delete"
        assert data["action"] == "block"

    def test_list_rules(self, client):
        client.post(
            "/api/agents",
            json={"id": "agent-1", "name": "Agent 1"},
        )
        client.post(
            "/api/agents/agent-1/rules",
            json={"name": "rule-1", "action": "block", "tool": "t"},
        )

        response = client.get("/api/agents/agent-1/rules")
        assert response.status_code == 200
        rules = response.json()
        assert len(rules) >= 1

    def test_delete_rule(self, client):
        client.post(
            "/api/agents",
            json={"id": "agent-1", "name": "Agent 1"},
        )
        create_resp = client.post(
            "/api/agents/agent-1/rules",
            json={"name": "rule-1", "action": "block", "tool": "t"},
        )
        rule_id = create_resp.json()["id"]

        response = client.delete(f"/api/agents/agent-1/rules/{rule_id}")
        assert response.status_code == 200


class TestApprovalEndpoints:
    """Tests for /api/approvals endpoints."""

    def test_create_approval(self, client):
        client.post(
            "/api/agents",
            json={"id": "agent-1", "name": "Agent 1"},
        )

        response = client.post(
            "/api/approvals",
            json={
                "agent_id": "agent-1",
                "tool": "send_email",
                "params": {"to": "test@example.com"},
                "rule": {"name": "email-approval"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"

    def test_get_approval(self, client):
        client.post(
            "/api/agents",
            json={"id": "agent-1", "name": "Agent 1"},
        )
        create_resp = client.post(
            "/api/approvals",
            json={
                "agent_id": "agent-1",
                "tool": "send_email",
                "params": {},
                "rule": {},
            },
        )
        approval_id = create_resp.json()["id"]

        response = client.get(f"/api/approvals/{approval_id}")
        assert response.status_code == 200

    def test_approve(self, client):
        client.post(
            "/api/agents",
            json={"id": "agent-1", "name": "Agent 1"},
        )
        create_resp = client.post(
            "/api/approvals",
            json={
                "agent_id": "agent-1",
                "tool": "send_email",
                "params": {},
                "rule": {},
            },
        )
        approval_id = create_resp.json()["id"]

        response = client.post(f"/api/approvals/{approval_id}/approve")
        assert response.status_code == 200
        assert response.json()["status"] == "approved"

    def test_reject(self, client):
        client.post(
            "/api/agents",
            json={"id": "agent-1", "name": "Agent 1"},
        )
        create_resp = client.post(
            "/api/approvals",
            json={
                "agent_id": "agent-1",
                "tool": "send_email",
                "params": {},
                "rule": {},
            },
        )
        approval_id = create_resp.json()["id"]

        response = client.post(f"/api/approvals/{approval_id}/reject")
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

    def test_list_approvals(self, client):
        client.post(
            "/api/agents",
            json={"id": "agent-1", "name": "Agent 1"},
        )
        client.post(
            "/api/approvals",
            json={
                "agent_id": "agent-1",
                "tool": "send_email",
                "params": {},
                "rule": {},
            },
        )

        response = client.get("/api/approvals")
        assert response.status_code == 200


class TestAuditEndpoints:
    """Tests for /api/audit endpoints."""

    def test_log_audit(self, client):
        response = client.post(
            "/api/audit",
            json={
                "agent_id": "agent-1",
                "tool": "search",
                "params": {"q": "test"},
                "status": "success",
                "cost": 0.01,
                "duration_ms": 100.0,
            },
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_list_audit(self, client):
        client.post(
            "/api/audit",
            json={
                "agent_id": "agent-1",
                "tool": "search",
                "params": {},
                "status": "success",
            },
        )

        response = client.get("/api/audit")
        assert response.status_code == 200
        events = response.json()
        assert len(events) >= 1
