"""Approval client for human-in-the-loop controls — framework-agnostic."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urljoin

import httpx

from .models import ApprovalRequest


class ApprovalClient:
    """Requests and polls for human approvals.

    Default behavior: request approval, then poll until resolved or timeout.
    If the server is unreachable, defaults to deny (fail-closed).
    """

    def __init__(self, server_url: str, api_key: str | None = None):
        self.server_url = server_url
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def request(
        self,
        agent_id: str,
        tool: str,
        params: dict[str, Any],
        rule: dict[str, Any],
        timeout_seconds: float = 300.0,
        poll_interval: float = 2.0,
    ) -> bool:
        """Request approval and block until resolved or timeout.

        Returns True if approved, False if rejected or timed out.
        """
        # 1. Create approval request
        payload = {
            "agent_id": agent_id,
            "tool": tool,
            "params": params,
            "rule": rule,
        }
        try:
            resp = httpx.post(
                urljoin(self.server_url, "/api/approvals"),
                json=payload,
                headers=self._headers(),
                timeout=10.0,
            )
            resp.raise_for_status()
            approval = resp.json()
            approval_id = approval["id"]
        except Exception as exc:
            # If server is unreachable, default to deny (fail-closed)
            print(f"[Anqush] Approval request failed: {exc}")
            return False

        # 2. Poll for resolution
        start = time.time()
        while time.time() - start < timeout_seconds:
            try:
                resp = httpx.get(
                    urljoin(self.server_url, f"/api/approvals/{approval_id}"),
                    headers=self._headers(),
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    status = resp.json().get("status")
                    if status == "approved":
                        return True
                    if status == "rejected":
                        return False
            except Exception:
                pass
            time.sleep(poll_interval)

        # Timeout — treat as rejected
        return False
