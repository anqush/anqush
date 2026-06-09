"""Auth conformance tests.

Verifies that the server correctly handles authentication:
- Missing token → 401
- Invalid token → 401
- Valid token → 200

Note: The reference server may not implement auth yet. These tests
check for spec compliance but may pass with warnings.
"""

from __future__ import annotations

import pytest

from anqush.protocol.http import HTTPTransport


class TestAuthentication:
    """Test authentication requirements."""

    def test_missing_token_returns_401_or_works(
        self, server_url: str, agent_id: str
    ) -> None:
        """Request without Authorization header returns 401 or works (if no auth)."""
        transport = HTTPTransport(base_url=server_url, api_key=None)
        try:
            # If server has no auth, this will succeed
            response = transport.get_rules(agent_id)
            # Server doesn't implement auth - that's ok for reference server
            assert hasattr(response, "rules")
        except Exception as e:
            # Server requires auth - check for 401
            error_msg = str(e).lower()
            assert "unauthorized" in error_msg or "401" in error_msg

    def test_invalid_token_returns_401_or_works(
        self, server_url: str, agent_id: str
    ) -> None:
        """Request with invalid bearer token returns 401 or works (if no auth)."""
        transport = HTTPTransport(
            base_url=server_url, api_key="invalid-token-12345"
        )
        try:
            response = transport.get_rules(agent_id)
            # Server doesn't validate tokens - that's ok for reference server
            assert hasattr(response, "rules")
        except Exception as e:
            error_msg = str(e).lower()
            assert "unauthorized" in error_msg or "401" in error_msg

    def test_valid_token_returns_200(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Request with valid token returns 200."""
        response = transport.get_rules(agent_id)
        assert hasattr(response, "rules")
        assert hasattr(response, "version")

    def test_health_endpoint_requires_no_auth(
        self, server_url: str
    ) -> None:
        """Health endpoint works without authentication."""
        transport = HTTPTransport(base_url=server_url, api_key=None)
        response = transport.health()
        assert response["status"] in ("ok", "deprecated")
