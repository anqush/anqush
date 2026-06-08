"""Budget tracker for agent tool calls — framework-agnostic."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx

from .models import BudgetExceededError


# ─── Cost rates per 1K tokens (rough estimates) ──────────────────────────────

DEFAULT_COST_RATES: dict[str, float] = {
    "gpt-4o": 0.005,
    "gpt-4o-mini": 0.00015,
    "gpt-4-turbo": 0.01,
    "gpt-4": 0.03,
    "gpt-3.5-turbo": 0.0005,
    "claude-3-5-sonnet": 0.003,
    "claude-3-opus": 0.015,
    "claude-3-haiku": 0.00025,
}


class BudgetTracker:
    """Tracks spending and enforces budget limits.

    Supports both server-backed budgets (fetched from the control plane)
    and local budget limits.
    """

    def __init__(
        self,
        server_url: str,
        api_key: str | None = None,
        cost_rates: dict[str, float] | None = None,
    ):
        self.server_url = server_url
        self.api_key = api_key
        self.cost_rates = cost_rates or DEFAULT_COST_RATES

        # Local budget limits (can be overridden by server)
        self._max_session_cost: float | None = None
        self._max_daily_cost: float | None = None

        # Tracked spend
        self._session_spend: float = 0.0

        # Server state
        self._budget_fetched: bool = False

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def set_limits(self, max_session_cost: float | None, max_daily_cost: float | None) -> None:
        """Set local budget limits."""
        self._max_session_cost = max_session_cost
        self._max_daily_cost = max_daily_cost

    def check_budget(self, estimated_cost: float) -> None:
        """Check if adding estimated_cost would exceed session budget.

        Raises BudgetExceededError if the budget would be exceeded.
        """
        if self._max_session_cost is None:
            self._fetch_budget()

        if self._max_session_cost and (self._session_spend + estimated_cost) > self._max_session_cost:
            raise BudgetExceededError(
                budget=self._max_session_cost,
                current=self._session_spend,
                requested=estimated_cost,
            )

    def record_spend(self, cost: float) -> None:
        """Record actual spend after a successful tool call."""
        self._session_spend += cost

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate from text (4 chars ≈ 1 token)."""
        return len(text) // 4

    def estimate_cost(self, model: str, tokens: int) -> float:
        """Estimate cost for a given model and token count."""
        rate = self.cost_rates.get(model, 0.005)
        return (tokens / 1000) * rate

    def estimate_call_cost(self, model: str, messages: list[dict[str, Any]]) -> float:
        """Estimate cost for a chat completion call."""
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        tokens = self.estimate_tokens("x" * total_chars)
        return self.estimate_cost(model, tokens)

    def _fetch_budget(self) -> None:
        """Fetch budget limits from the control plane."""
        if self._budget_fetched:
            return
        self._budget_fetched = True

        try:
            # We need an agent_id to fetch budget, but this is called
            # from the adapter which knows the agent_id. For now, we
            # just mark as fetched and let the adapter pass agent_id.
            pass
        except Exception:
            pass

    def fetch_budget_for_agent(self, agent_id: str) -> None:
        """Fetch budget limits from the control plane for a specific agent."""
        try:
            resp = httpx.get(
                urljoin(self.server_url, f"/api/agents/{agent_id}/budget"),
                headers=self._headers(),
                timeout=2.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                if self._max_session_cost is None:
                    self._max_session_cost = data.get("max_session_cost")
                if self._max_daily_cost is None:
                    self._max_daily_cost = data.get("max_daily_cost")
        except Exception:
            pass

    @property
    def session_spend(self) -> float:
        """Current session spend."""
        return self._session_spend

    @property
    def max_session_cost(self) -> float | None:
        """Session budget limit."""
        return self._max_session_cost
