"""Shared fixtures for Anqush Protocol conformance tests.

These tests verify that a server implements the Anqush Protocol correctly.
Run against the reference server or any conformant implementation.

Usage:
    # Against local reference server (default)
    pytest tests/test_protocol/

    # Against a specific server
    ANQUSH_URL=https://their-server.example.com \\
    ANQUSH_API_KEY=their-test-key \\
    pytest tests/test_protocol/
"""

from __future__ import annotations

import os

import pytest

from anqush.protocol.http import HTTPTransport


from anqush.protocol.transport import Transport


# Automatically mark all protocol tests as requiring a live server
# Run with: pytest -m "not protocol" to skip
# Run with: pytest -m protocol to run only contract tests
def pytest_collection_modifyitems(config, items):
    for item in items:
        if "test_protocol" in item.nodeid:
            item.add_marker("protocol")


@pytest.fixture
def server_url() -> str:
    """Server URL from env or default to local reference server."""
    return os.getenv("ANQUSH_URL", "http://localhost:8000")


@pytest.fixture
def api_key() -> str:
    """API key from env or default test key."""
    return os.getenv("ANQUSH_API_KEY", "test-key")


@pytest.fixture
def transport(server_url: str, api_key: str) -> Transport:
    """HTTP transport configured for the target server."""
    return HTTPTransport(base_url=server_url, api_key=api_key)


@pytest.fixture
def unauthenticated_transport(server_url: str) -> Transport:
    """HTTP transport without auth (for testing 401 responses)."""
    return HTTPTransport(base_url=server_url, api_key=None)


@pytest.fixture
def agent_id() -> str:
    """Test agent ID. The server must have this agent created."""
    return os.getenv("ANQUSH_TEST_AGENT_ID", "test-agent")


@pytest.fixture
def test_rule() -> dict:
    """A rule to create for testing."""
    return {
        "name": "test-block-delete",
        "action": "block",
        "tool": "db.delete",
        "reason": "Test rule: block deletes",
    }
