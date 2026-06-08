"""Tests for anqush.core.budget."""

import pytest

from anqush.core.budget import BudgetTracker, DEFAULT_COST_RATES
from anqush.core.models import BudgetExceededError


class TestBudgetTracker:
    """Tests for BudgetTracker."""

    def test_creation(self, server_url):
        tracker = BudgetTracker(server_url)
        assert tracker.session_spend == 0.0
        assert tracker.max_session_cost is None

    def test_set_limits(self, server_url):
        tracker = BudgetTracker(server_url)
        tracker.set_limits(max_session_cost=100.0, max_daily_cost=500.0)
        assert tracker.max_session_cost == 100.0

    def test_estimate_tokens(self, server_url):
        tracker = BudgetTracker(server_url)
        # ~4 chars per token
        assert tracker.estimate_tokens("1234") == 1
        assert tracker.estimate_tokens("12345678") == 2

    def test_estimate_cost(self, server_url):
        tracker = BudgetTracker(server_url)
        # gpt-4o: $0.005 per 1K tokens
        cost = tracker.estimate_cost("gpt-4o", 1000)
        assert cost == pytest.approx(0.005)

    def test_estimate_cost_unknown_model(self, server_url):
        tracker = BudgetTracker(server_url)
        # Unknown model uses default rate
        cost = tracker.estimate_cost("unknown-model", 1000)
        assert cost == pytest.approx(0.005)

    def test_estimate_call_cost(self, server_url):
        tracker = BudgetTracker(server_url)
        messages = [{"content": "This is a longer message that should result in some tokens being estimated"}]
        cost = tracker.estimate_call_cost("gpt-4o", messages)
        assert cost > 0

    def test_check_budget_no_limit(self, server_url):
        tracker = BudgetTracker(server_url)
        # No limit set, should not raise
        tracker.check_budget(1000.0)

    def test_check_budget_within_limit(self, server_url):
        tracker = BudgetTracker(server_url)
        tracker.set_limits(max_session_cost=10.0, max_daily_cost=None)
        tracker.check_budget(5.0)  # Should not raise

    def test_check_budget_exceeds_limit(self, server_url):
        tracker = BudgetTracker(server_url)
        tracker.set_limits(max_session_cost=10.0, max_daily_cost=None)
        tracker._session_spend = 8.0

        with pytest.raises(BudgetExceededError) as exc_info:
            tracker.check_budget(5.0)
        assert exc_info.value.budget == 10.0
        assert exc_info.value.current == 8.0
        assert exc_info.value.requested == 5.0

    def test_record_spend(self, server_url):
        tracker = BudgetTracker(server_url)
        tracker.record_spend(1.5)
        assert tracker.session_spend == 1.5
        tracker.record_spend(2.5)
        assert tracker.session_spend == 4.0


class TestDefaultCostRates:
    """Tests for default cost rates."""

    def test_has_common_models(self):
        assert "gpt-4o" in DEFAULT_COST_RATES
        assert "gpt-4o-mini" in DEFAULT_COST_RATES
        assert "claude-3-5-sonnet" in DEFAULT_COST_RATES

    def test_rates_are_positive(self):
        for model, rate in DEFAULT_COST_RATES.items():
            assert rate > 0, f"Rate for {model} should be positive"
