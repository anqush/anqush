"""Budget conformance tests.

Verifies that the server correctly implements budget fetching:
- Response shape matches spec
- Nullable limits work correctly
- Currency field is present
"""

from __future__ import annotations

import pytest

from anqush.protocol.transport import Transport
from anqush.protocol.types import BudgetResponse


class TestBudgetFetch:
    """Test GET /agents/{agent_id}/budget."""

    def test_returns_budget_response(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Response has all required fields."""
        response = transport.get_budget(agent_id)
        assert isinstance(response, BudgetResponse)
        assert response.agent_id == agent_id
        assert isinstance(response.session_spend, (int, float))
        assert isinstance(response.daily_spend, (int, float))
        assert isinstance(response.currency, str)

    def test_nullable_limits(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Limits can be null (no cap)."""
        response = transport.get_budget(agent_id)
        # max_session_cost and max_daily_cost can be None or float
        assert response.max_session_cost is None or isinstance(
            response.max_session_cost, (int, float)
        )
        assert response.max_daily_cost is None or isinstance(
            response.max_daily_cost, (int, float)
        )

    def test_spend_non_negative(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Spend values are non-negative."""
        response = transport.get_budget(agent_id)
        assert response.session_spend >= 0
        assert response.daily_spend >= 0

    def test_currency_is_string(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Currency is a non-empty string."""
        response = transport.get_budget(agent_id)
        assert isinstance(response.currency, str)
        assert len(response.currency) > 0

    def test_agent_not_found_returns_error(
        self, transport: Transport
    ) -> None:
        """Non-existent agent returns error or default budget."""
        try:
            response = transport.get_budget("non-existent-agent-xyz")
            # Server returns default budget for unknown agents
            assert isinstance(response, BudgetResponse)
        except Exception as e:
            # Server returns 404 for unknown agents
            error_msg = str(e).lower()
            assert "not_found" in error_msg or "agent_not_found" in error_msg or "404" in error_msg
