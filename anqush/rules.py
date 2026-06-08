"""Rule engine for runtime controls."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

import httpx
import yaml


class RuleEngine:
    """Fetches and evaluates runtime rules from the control plane."""

    def __init__(self, server_url: str, api_key: str | None = None):
        self.server_url = server_url
        self.api_key = api_key
        self._rules: list[dict] = []
        self._load_local_rules()

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _load_local_rules(self) -> None:
        """Load rules from local anqush.yaml if present."""
        path = os.getenv("ANQUSH_RULES", "anqush.yaml")
        if os.path.exists(path):
            with open(path) as f:
                data = yaml.safe_load(f)
                if data:
                    self._rules = data.get("rules", [])

    def fetch_remote_rules(self, agent_id: str) -> list[dict]:
        """Fetch rules from the control plane."""
        try:
            resp = httpx.get(
                urljoin(self.server_url, f"/api/agents/{agent_id}/rules"),
                headers=self._headers(),
                timeout=3.0,
            )
            if resp.status_code == 200:
                self._rules = resp.json().get("rules", [])
        except Exception:
            pass  # Fall back to local rules
        return self._rules

    def check_block(self, tool: str, params: dict[str, Any]) -> str | None:
        """Return block reason if tool is blocked, else None."""
        for rule in self._rules:
            if rule.get("action") != "block":
                continue
            if self._matches(rule, tool, params):
                return rule.get("reason", f"Blocked by rule: {rule.get('name', 'unnamed')}")
        return None

    def check_approval(self, tool: str, params: dict[str, Any]) -> dict | None:
        """Return approval rule dict if approval required, else None."""
        for rule in self._rules:
            if rule.get("action") != "approval":
                continue
            if self._matches(rule, tool, params):
                return rule
        return None

    def _matches(self, rule: dict, tool: str, params: dict[str, Any]) -> bool:
        """Check if a rule matches the tool call."""
        # Tool name match (supports wildcards)
        rule_tool = rule.get("tool", "*")
        if rule_tool != "*" and not self._match_tool(rule_tool, tool):
            return False

        # Parameter conditions
        conditions = rule.get("when", {})
        for key, condition in conditions.items():
            value = self._get_nested(params, key)
            if not self._eval_condition(condition, value):
                return False

        return True

    def _match_tool(self, pattern: str, tool: str) -> bool:
        """Match tool name, supporting * wildcards."""
        if pattern.endswith(".*"):
            return tool.startswith(pattern[:-2] + ".")
        return pattern == tool

    def _get_nested(self, data: dict, path: str) -> Any:
        """Get nested dict value by dot-path."""
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def _eval_condition(self, condition: Any, value: Any) -> bool:
        """Evaluate a condition against a value."""
        if isinstance(condition, dict):
            for op, target in condition.items():
                if op == "eq" and value != target:
                    return False
                if op == "ne" and value == target:
                    return False
                if op == "gt" and (value is None or value <= target):
                    return False
                if op == "gte" and (value is None or value < target):
                    return False
                if op == "lt" and (value is None or value >= target):
                    return False
                if op == "lte" and (value is None or value > target):
                    return False
                if op == "in" and value not in target:
                    return False
                if op == "contains" and (value is None or target not in value):
                    return False
                if op == "starts_with" and (value is None or not str(value).startswith(target)):
                    return False
            return True
        # Simple equality
        return value == condition


def load_rules(path: str) -> list[dict]:
    """Load rules from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("rules", []) if data else []
