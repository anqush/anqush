"""Shared test fixtures for Anqush tests."""

from __future__ import annotations

import os
import tempfile
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def server_url() -> str:
    """Anqush server URL for tests."""
    return "http://localhost:8000"


@pytest.fixture
def api_key() -> str:
    """API key for tests."""
    return "test-api-key-12345"


@pytest.fixture
def agent_id() -> str:
    """Agent ID for tests."""
    return "test-agent"


@pytest.fixture
def sample_rules() -> list[dict]:
    """Sample rules for testing."""
    return [
        {
            "name": "block-delete",
            "action": "block",
            "tool": "delete_file",
            "reason": "File deletion not allowed",
        },
        {
            "name": "block-wildcard",
            "action": "block",
            "tool": "admin.*",
            "reason": "Admin tools blocked",
        },
        {
            "name": "approve-refund",
            "action": "approval",
            "tool": "process_refund",
            "when": {"amount": {"gt": 100}},
            "reason": "Large refunds require approval",
        },
        {
            "name": "approve-email",
            "action": "approval",
            "tool": "send_email",
            "reason": "All emails require approval",
        },
    ]


@pytest.fixture
def sample_tool_params() -> dict:
    """Sample tool parameters."""
    return {"query": "test search", "limit": 10}


@pytest.fixture
def tmp_db() -> Generator[str, None, None]:
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    os.unlink(db_path)


@pytest.fixture
def mock_httpx():
    """Mock httpx for testing HTTP calls."""
    with patch("anqush.core.rules.httpx") as mock:
        yield mock


@pytest.fixture
def mock_audit_httpx():
    """Mock httpx for audit logging."""
    with patch("anqush.core.audit.httpx") as mock:
        yield mock


@pytest.fixture
def mock_approvals_httpx():
    """Mock httpx for approval requests."""
    with patch("anqush.core.approvals.httpx") as mock:
        yield mock


@pytest.fixture
def mock_budget_httpx():
    """Mock httpx for budget fetching."""
    with patch("anqush.core.budget.httpx") as mock:
        yield mock
