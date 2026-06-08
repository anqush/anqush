"""Anqush Protocol conformance test suite.

This module provides a unified way to run all conformance tests against
a server. Use this to verify protocol compliance.

Usage:
    # Run all conformance tests
    pytest tests/test_protocol/

    # Run against a specific server
    ANQUSH_URL=https://their-server.example.com \\
    ANQUSH_API_KEY=their-test-key \\
    pytest tests/test_protocol/

    # Run from code
    from tests.test_protocol.conformance import run_conformance
    result = run_conformance("http://localhost:8000", "api-key")
    print(result)
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from anqush.protocol.http import HTTPTransport


@dataclass
class ConformanceResult:
    """Result of running the conformance suite."""

    passed: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    server_url: str = ""
    passed_all: bool = False

    @property
    def success(self) -> bool:
        return self.failed == 0 and self.passed > 0


def check_server_reachable(url: str, api_key: Optional[str] = None) -> bool:
    """Quick check if server is reachable."""
    try:
        transport = HTTPTransport(base_url=url, api_key=api_key)
        transport.health()
        return True
    except Exception:
        return False


def run_conformance(
    server_url: str,
    api_key: str,
    agent_id: str = "test-agent",
    verbose: bool = True,
) -> ConformanceResult:
    """Run the full conformance test suite against a server.

    Args:
        server_url: Base URL of the server to test
        api_key: API key for authentication
        agent_id: Agent ID to use for testing (must exist on server)
        verbose: Whether to print detailed output

    Returns:
        ConformanceResult with pass/fail counts
    """
    result = ConformanceResult(server_url=server_url)

    # Check server is reachable
    if not check_server_reachable(server_url, api_key):
        result.errors.append(f"Server at {server_url} is not reachable")
        return result

    # Run pytest
    test_dir = Path(__file__).parent
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_dir),
        "-v",
        "--tb=short",
    ]

    env = {
        "ANQUSH_URL": server_url,
        "ANQUSH_API_KEY": api_key,
        "ANQUSH_TEST_AGENT_ID": agent_id,
    }

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env={**dict(__import__("os").environ), **env},
        )

        if verbose:
            print(proc.stdout)
            if proc.stderr:
                print(proc.stderr, file=sys.stderr)

        # Parse results
        if "passed" in proc.stdout:
            for line in proc.stdout.split("\n"):
                if "passed" in line and "failed" in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if "passed" in part:
                            result.passed = int(parts[i - 1])
                        if "failed" in part:
                            result.failed = int(parts[i - 1])
                elif "passed" in line and "failed" not in line:
                    for part in line.split():
                        if part.isdigit():
                            result.passed = int(part)
                            break

        result.passed_all = result.success

    except Exception as e:
        result.errors.append(f"Failed to run tests: {e}")

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Anqush Protocol conformance tests")
    parser.add_argument("--url", default="http://localhost:8000", help="Server URL")
    parser.add_argument("--api-key", default="test-key", help="API key")
    parser.add_argument("--agent-id", default="test-agent", help="Test agent ID")
    args = parser.parse_args()

    result = run_conformance(args.url, args.api_key, args.agent_id)
    sys.exit(0 if result.success else 1)
