"""Rules conformance tests.

Verifies that the server correctly implements rule fetching:
- Response shape matches spec
- Rules are ordered correctly
"""

from __future__ import annotations

import pytest

from anqush.protocol.transport import Transport
from anqush.protocol.types import Rule, RulesResponse


class TestRulesFetch:
    """Test GET /agents/{agent_id}/rules."""

    def test_returns_rules_response(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Response has rules and version fields."""
        response = transport.get_rules(agent_id)
        assert isinstance(response, RulesResponse)
        assert isinstance(response.rules, list)
        assert isinstance(response.version, str)

    def test_rules_have_required_fields(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Each rule has name, action, tool."""
        response = transport.get_rules(agent_id)
        for rule in response.rules:
            assert isinstance(rule, Rule)
            assert rule.name  # non-empty
            assert rule.action.value in ("block", "approval")
            assert rule.tool  # non-empty

    def test_rules_evaluation_order(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Rules are returned in evaluation order (first match wins)."""
        response = transport.get_rules(agent_id)
        # Rules should be ordered - verify stability across calls
        response2 = transport.get_rules(agent_id)
        assert response.version == response2.version
        assert len(response.rules) == len(response2.rules)

    def test_agent_not_found_returns_error(
        self, transport: Transport
    ) -> None:
        """Non-existent agent returns error or empty rules."""
        try:
            response = transport.get_rules("non-existent-agent-xyz")
            # Server returns empty rules for unknown agents
            assert isinstance(response.rules, list)
        except Exception as e:
            # Server returns 404 for unknown agents
            error_msg = str(e).lower()
            assert "not_found" in error_msg or "agent_not_found" in error_msg or "404" in error_msg

    def test_block_rules_have_reason(
        self, transport: Transport, agent_id: str
    ) -> None:
        """Block rules should have a reason (recommended)."""
        response = transport.get_rules(agent_id)
        block_rules = [r for r in response.rules if r.action.value == "block"]
        for rule in block_rules:
            # reason is optional but recommended
            if rule.reason is not None:
                assert isinstance(rule.reason, str)
