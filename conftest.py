"""Root conftest: initialise an in-memory test database for every test session.

All modules that call agent.db functions will use this temporary DB,
preventing test pollution and fixing the 'no such table' errors when the
pipeline calls get_search_config() → db.get_search_overrides().
"""
import tempfile
from pathlib import Path

import pytest

import agent.db as _db


@pytest.fixture(autouse=True)
def _init_test_db(tmp_path, monkeypatch):
    """Point agent.db at a fresh per-test SQLite file and initialise schema."""
    db_path = tmp_path / "test_jobs.db"
    monkeypatch.setattr(_db, "DB_PATH", db_path)
    _db.init_db()
    yield
