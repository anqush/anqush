"""Tests for anqush.core.audit."""

import pytest

from anqush.core.audit import AuditLogger
from anqush.core.models import AuditEvent


class TestAuditLogger:
    """Tests for AuditLogger."""

    def test_creation(self, server_url):
        logger = AuditLogger(server_url)
        assert logger.server_url == server_url
        assert logger.api_key is None

    def test_creation_with_api_key(self, server_url, api_key):
        logger = AuditLogger(server_url, api_key)
        assert logger.api_key == api_key

    def test_headers_with_api_key(self, server_url, api_key):
        logger = AuditLogger(server_url, api_key)
        headers = logger._headers()
        assert headers["Authorization"] == f"Bearer {api_key}"

    def test_headers_without_api_key(self, server_url):
        logger = AuditLogger(server_url)
        headers = logger._headers()
        assert "Authorization" not in headers

    def test_log_sends_event(self, server_url, mock_audit_httpx):
        logger = AuditLogger(server_url)
        logger.log(
            agent_id="test",
            tool="search",
            params={"q": "test"},
            result="result",
            status="success",
            reason=None,
            cost=0.01,
            duration_ms=100.0,
        )
        mock_audit_httpx.post.assert_called_once()
        call_args = mock_audit_httpx.post.call_args
        assert "/api/audit" in call_args[0][0]

    def test_log_truncates_large_result(self, server_url, mock_audit_httpx):
        logger = AuditLogger(server_url)
        large_result = "x" * 5000
        logger.log(
            agent_id="test",
            tool="search",
            params={},
            result=large_result,
            status="success",
            reason=None,
            cost=0.0,
            duration_ms=0.0,
        )
        call_args = mock_audit_httpx.post.call_args
        payload = call_args[1]["json"]
        assert len(payload["result"]) < 5000
        assert "truncated" in payload["result"]

    def test_log_event(self, server_url, mock_audit_httpx):
        logger = AuditLogger(server_url)
        event = AuditEvent(
            agent_id="test",
            tool="search",
            params={},
            status="success",
        )
        logger.log_event(event)
        mock_audit_httpx.post.assert_called_once()

    def test_log_swallows_errors(self, server_url, mock_audit_httpx):
        mock_audit_httpx.post.side_effect = Exception("Network error")
        logger = AuditLogger(server_url)
        # Should not raise
        logger.log(
            agent_id="test",
            tool="search",
            params={},
            result=None,
            status="error",
            reason="failed",
            cost=0.0,
            duration_ms=0.0,
        )

    def test_truncate_none(self, server_url):
        logger = AuditLogger(server_url)
        assert logger._truncate(None) is None

    def test_truncate_short(self, server_url):
        logger = AuditLogger(server_url)
        assert logger._truncate("hello") == "hello"

    def test_truncate_long(self, server_url):
        logger = AuditLogger(server_url)
        long_str = "x" * 5000
        result = logger._truncate(long_str)
        assert len(result) < 5000
        assert "truncated" in result
