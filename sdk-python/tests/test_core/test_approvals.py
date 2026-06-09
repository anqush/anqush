"""Tests for anqush.core.approvals."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from anqush.core.approvals import ApprovalClient


class TestApprovalClient:
    """Tests for ApprovalClient."""

    def test_creation(self, server_url):
        client = ApprovalClient(server_url)
        assert client.server_url == server_url
        assert client.api_key is None

    def test_creation_with_api_key(self, server_url, api_key):
        client = ApprovalClient(server_url, api_key)
        assert client.api_key == api_key

    def test_headers_with_api_key(self, server_url, api_key):
        client = ApprovalClient(server_url, api_key)
        headers = client._headers()
        assert headers["Authorization"] == f"Bearer {api_key}"

    def test_headers_without_api_key(self, server_url):
        client = ApprovalClient(server_url)
        headers = client._headers()
        assert "Authorization" not in headers

    def test_request_creates_approval(self, server_url, mock_approvals_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "abc-123", "status": "pending"}
        mock_response.raise_for_status = MagicMock()
        mock_approvals_httpx.post.return_value = mock_response

        # Mock poll response
        mock_poll_response = MagicMock()
        mock_poll_response.status_code = 200
        mock_poll_response.json.return_value = {"status": "approved"}
        mock_approvals_httpx.get.return_value = mock_poll_response

        client = ApprovalClient(server_url)
        result = client.request(
            agent_id="test",
            tool="send_email",
            params={"to": "test@example.com"},
            rule={"name": "email-approval"},
            timeout_seconds=5.0,
            poll_interval=0.1,
        )

        assert result is True
        mock_approvals_httpx.post.assert_called_once()

    def test_request_deny_on_server_error(self, server_url, mock_approvals_httpx):
        mock_approvals_httpx.post.side_effect = Exception("Connection refused")

        client = ApprovalClient(server_url)
        result = client.request(
            agent_id="test",
            tool="send_email",
            params={},
            rule={},
            timeout_seconds=1.0,
            poll_interval=0.1,
        )

        assert result is False  # Fail-closed

    def test_request_timeout(self, server_url, mock_approvals_httpx):
        # Mock successful creation
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "abc-123", "status": "pending"}
        mock_response.raise_for_status = MagicMock()
        mock_approvals_httpx.post.return_value = mock_response

        # Mock poll that always returns pending
        mock_poll_response = MagicMock()
        mock_poll_response.status_code = 200
        mock_poll_response.json.return_value = {"status": "pending"}
        mock_approvals_httpx.get.return_value = mock_poll_response

        client = ApprovalClient(server_url)
        result = client.request(
            agent_id="test",
            tool="send_email",
            params={},
            rule={},
            timeout_seconds=0.5,
            poll_interval=0.1,
        )

        assert result is False  # Timeout = rejected

    def test_request_rejection(self, server_url, mock_approvals_httpx):
        # Mock successful creation
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "abc-123", "status": "pending"}
        mock_response.raise_for_status = MagicMock()
        mock_approvals_httpx.post.return_value = mock_response

        # Mock poll that returns rejected
        mock_poll_response = MagicMock()
        mock_poll_response.status_code = 200
        mock_poll_response.json.return_value = {"status": "rejected"}
        mock_approvals_httpx.get.return_value = mock_poll_response

        client = ApprovalClient(server_url)
        result = client.request(
            agent_id="test",
            tool="send_email",
            params={},
            rule={},
            timeout_seconds=5.0,
            poll_interval=0.1,
        )

        assert result is False
