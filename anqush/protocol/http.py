"""HTTP transport for the Anqush Protocol.

Talks to a real Anqush control plane over HTTP.
Handles both spec-compliant and legacy server responses.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx

from .transport import Transport
from .types import (
    ApprovalCreateRequest,
    ApprovalResponse,
    AuditAcceptedResponse,
    AuditEvent,
    AuditEventBatch,
    BudgetResponse,
    ErrorResponse,
    RulesResponse,
)


class HTTPTransport(Transport):
    """HTTP client that implements the Anqush Protocol.

    Usage:
        transport = HTTPTransport(
            base_url="http://localhost:8000",
            api_key="ak_proj_abc123",
        )
        rules = transport.get_rules("my-agent")
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def _url(self, path: str) -> str:
        """Build full URL from path."""
        return f"{self.base_url}{path}"

    def _headers(self) -> dict[str, str]:
        """Build request headers with auth."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _handle_error(self, resp: httpx.Response) -> None:
        """Raise on 4xx/5xx."""
        if resp.status_code >= 400:
            # Try to parse structured error
            try:
                error = ErrorResponse(**resp.json())
                raise Exception(f"[{error.code}] {error.message}")
            except (KeyError, ValueError):
                # Fall back to generic error
                raise Exception(f"HTTP {resp.status_code}")

    # ─── Rules ────────────────────────────────────────────────────────────────

    def get_rules(self, agent_id: str) -> RulesResponse:
        resp = self._client.get(
            self._url(f"/api/agents/{agent_id}/rules"),
            headers=self._headers(),
        )
        self._handle_error(resp)
        data = resp.json()

        # Handle both spec-compliant and legacy responses
        if isinstance(data, list):
            # Legacy: server returns rules array directly
            return RulesResponse(rules=data, version="1")
        elif isinstance(data, dict):
            # Spec-compliant: server returns {rules: [...], version: "..."}
            if "version" not in data:
                data["version"] = "1"
            return RulesResponse(**data)
        else:
            raise Exception(f"Unexpected response format: {type(data)}")

    # ─── Budget ───────────────────────────────────────────────────────────────

    def get_budget(self, agent_id: str) -> BudgetResponse:
        resp = self._client.get(
            self._url(f"/api/agents/{agent_id}/budget"),
            headers=self._headers(),
        )
        self._handle_error(resp)
        data = resp.json()

        # Handle missing currency field
        if "currency" not in data:
            data["currency"] = "USD"

        return BudgetResponse(**data)

    # ─── Approvals ────────────────────────────────────────────────────────────

    def create_approval(self, request: ApprovalCreateRequest) -> ApprovalResponse:
        resp = self._client.post(
            self._url("/api/approvals"),
            json=request.model_dump(exclude_none=True),
            headers=self._headers(),
        )
        self._handle_error(resp)
        return ApprovalResponse(**resp.json())

    def get_approval(self, approval_id: str) -> ApprovalResponse:
        resp = self._client.get(
            self._url(f"/api/approvals/{approval_id}"),
            headers=self._headers(),
        )
        self._handle_error(resp)
        return ApprovalResponse(**resp.json())

    # ─── Audit ────────────────────────────────────────────────────────────────

    def submit_audit(self, event: AuditEvent) -> AuditAcceptedResponse:
        resp = self._client.post(
            self._url("/api/audit"),
            json=event.model_dump(exclude_none=True),
            headers=self._headers(),
        )
        self._handle_error(resp)
        data = resp.json()

        # Handle both spec-compliant and legacy responses
        if "accepted" in data:
            return AuditAcceptedResponse(**data)
        elif "ok" in data:
            # Legacy: server returns {ok: true}
            return AuditAcceptedResponse(accepted=1)
        else:
            return AuditAcceptedResponse(accepted=1)

    def submit_audit_batch(self, batch: AuditEventBatch) -> AuditAcceptedResponse:
        resp = self._client.post(
            self._url("/api/audit"),
            json=batch.model_dump(exclude_none=True),
            headers=self._headers(),
        )
        self._handle_error(resp)
        data = resp.json()

        # Handle both spec-compliant and legacy responses
        if "accepted" in data:
            return AuditAcceptedResponse(**data)
        elif "ok" in data:
            return AuditAcceptedResponse(accepted=len(batch.events))
        else:
            return AuditAcceptedResponse(accepted=len(batch.events))

    # ─── Health ───────────────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        resp = self._client.get(self._url("/health"))
        self._handle_error(resp)
        return resp.json()

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> HTTPTransport:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
