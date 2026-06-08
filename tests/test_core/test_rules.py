"""Tests for anqush.core.rules."""

import pytest

from anqush.core.rules import RuleEngine, load_rules


class TestRuleEngine:
    """Tests for RuleEngine."""

    def test_empty_rules(self, server_url):
        engine = RuleEngine(server_url)
        assert engine._rules == []

    def test_check_block_no_rules(self, server_url):
        engine = RuleEngine(server_url)
        result = engine.check_block("any_tool", {})
        assert result is None

    def test_check_block_match(self, server_url, sample_rules):
        engine = RuleEngine(server_url)
        engine._rules = sample_rules

        result = engine.check_block("delete_file", {})
        assert result is not None
        assert "not allowed" in result

    def test_check_block_no_match(self, server_url, sample_rules):
        engine = RuleEngine(server_url)
        engine._rules = sample_rules

        result = engine.check_block("search", {})
        assert result is None

    def test_check_block_wildcard(self, server_url, sample_rules):
        engine = RuleEngine(server_url)
        engine._rules = sample_rules

        result = engine.check_block("admin.delete_user", {})
        assert result is not None
        assert "Admin tools blocked" in result

    def test_check_approval_no_rules(self, server_url):
        engine = RuleEngine(server_url)
        result = engine.check_approval("any_tool", {})
        assert result is None

    def test_check_approval_match(self, server_url, sample_rules):
        engine = RuleEngine(server_url)
        engine._rules = sample_rules

        result = engine.check_approval("send_email", {})
        assert result is not None
        assert result["name"] == "approve-email"

    def test_check_approval_with_condition_match(self, server_url, sample_rules):
        engine = RuleEngine(server_url)
        engine._rules = sample_rules

        result = engine.check_approval("process_refund", {"amount": 200})
        assert result is not None
        assert result["name"] == "approve-refund"

    def test_check_approval_with_condition_no_match(self, server_url, sample_rules):
        engine = RuleEngine(server_url)
        engine._rules = sample_rules

        result = engine.check_approval("process_refund", {"amount": 50})
        assert result is None


class TestRuleMatching:
    """Tests for rule matching logic."""

    def test_match_tool_exact(self, server_url):
        engine = RuleEngine(server_url)
        assert engine._match_tool("search", "search") is True
        assert engine._match_tool("search", "other") is False

    def test_match_tool_wildcard_prefix(self, server_url):
        engine = RuleEngine(server_url)
        assert engine._match_tool("admin.*", "admin.delete") is True
        assert engine._match_tool("admin.*", "admin.create") is True
        assert engine._match_tool("admin.*", "user.delete") is False

    def test_get_nested(self, server_url):
        engine = RuleEngine(server_url)
        data = {"a": {"b": {"c": 42}}}
        assert engine._get_nested(data, "a.b.c") == 42
        assert engine._get_nested(data, "a.b.d") is None
        assert engine._get_nested(data, "x.y") is None

    def test_eval_condition_eq(self, server_url):
        engine = RuleEngine(server_url)
        assert engine._eval_condition({"eq": "yes"}, "yes") is True
        assert engine._eval_condition({"eq": "yes"}, "no") is False

    def test_eval_condition_gt(self, server_url):
        engine = RuleEngine(server_url)
        assert engine._eval_condition({"gt": 100}, 200) is True
        assert engine._eval_condition({"gt": 100}, 50) is False
        assert engine._eval_condition({"gt": 100}, None) is False

    def test_eval_condition_gte(self, server_url):
        engine = RuleEngine(server_url)
        assert engine._eval_condition({"gte": 100}, 100) is True
        assert engine._eval_condition({"gte": 100}, 99) is False

    def test_eval_condition_lt(self, server_url):
        engine = RuleEngine(server_url)
        assert engine._eval_condition({"lt": 100}, 50) is True
        assert engine._eval_condition({"lt": 100}, 150) is False

    def test_eval_condition_lte(self, server_url):
        engine = RuleEngine(server_url)
        assert engine._eval_condition({"lte": 100}, 100) is True
        assert engine._eval_condition({"lte": 100}, 101) is False

    def test_eval_condition_in(self, server_url):
        engine = RuleEngine(server_url)
        assert engine._eval_condition({"in": ["a", "b"]}, "a") is True
        assert engine._eval_condition({"in": ["a", "b"]}, "c") is False

    def test_eval_condition_contains(self, server_url):
        engine = RuleEngine(server_url)
        assert engine._eval_condition({"contains": "hello"}, "say hello world") is True
        assert engine._eval_condition({"contains": "hello"}, "goodbye") is False

    def test_eval_condition_starts_with(self, server_url):
        engine = RuleEngine(server_url)
        assert engine._eval_condition({"starts_with": "http"}, "https://example.com") is True
        assert engine._eval_condition({"starts_with": "http"}, "ftp://example.com") is False

    def test_eval_condition_simple_equality(self, server_url):
        engine = RuleEngine(server_url)
        assert engine._eval_condition("yes", "yes") is True
        assert engine._eval_condition("yes", "no") is False


class TestLoadRules:
    """Tests for load_rules function."""

    def test_load_rules(self, tmp_path):
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text("""
rules:
  - name: test-rule
    action: block
    tool: test_tool
""")
        rules = load_rules(str(rules_file))
        assert len(rules) == 1
        assert rules[0]["name"] == "test-rule"

    def test_load_rules_empty(self, tmp_path):
        rules_file = tmp_path / "empty.yaml"
        rules_file.write_text("")
        rules = load_rules(str(rules_file))
        assert rules == []
