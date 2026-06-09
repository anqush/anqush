"""Shared test fixtures for Anqush Server tests."""

from __future__ import annotations

import tempfile
from typing import Generator

import pytest


@pytest.fixture
def tmp_db() -> Generator[str, None, None]:
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    import os
    os.unlink(db_path)
