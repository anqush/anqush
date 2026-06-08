"""Audit logger for agent actions — framework-agnostic."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx

from .models import AuditEvent


class AuditLogger:
    """Sends audit events to the control plane.

    Audit is best-effort — failures are silently ignored so they
    never break agent execution.
    """

    def __init__(self, server_url: str, api_key: str | None = None):
        self.server_url = server_url
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def log(
        self,
        agent_id: str,
        tool: str,
        params: dict[str, Any],
        result: Any,
        status: str,
        reason: str | None,
        cost: float,
        duration_ms: float,
    ) -> None:
        """Fire-and-forget audit event."""
        event = AuditEvent(
            agent_id=agent_id,
            tool=tool,
            params=params,
            result=self._truncate(result),
            status=status,
            reason=reason,
            cost=cost,
            duration_ms=duration_ms,
        )
        self._send(event)

    def log_event(self, event: AuditEvent) -> None:
        """Send a pre-built AuditEvent."""
        event.result = self._truncate(event.result)
        self._send(event)

    def _send(self, event: AuditEvent) -> None:
        """Send audit event to the control plane."""
        try:
            httpx.post(
                urljoin(self.server_url, "/api/audit"),
                json=event.to_dict(),
                headers=self._headers(),
                timeout=2.0,
            )
        except Exception:
            pass  # Audit is best-effort; don't break agent execution

    def _truncate(self, value: Any, max_len: int = 4000) -> Any:
        """Truncate large values for audit storage."""
        if value is None:
            return None
        s = str(value)
        if len(s) > max_len:
            return s[:max_len] + "... [truncated]"
        return value
