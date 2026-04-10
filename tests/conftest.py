"""Shared fixtures for the test suite.

The ``auto_db`` fixture patches agent.db.DB_PATH to a temporary file and
initialises the schema for every test.  Tests that need their own isolated
DB (e.g. test_db.py) can override DB_PATH again via their own fixture — the
last monkeypatch wins for that test's scope.
"""
import pytest
import agent.db as db_module


@pytest.fixture(autouse=True)
def auto_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a per-test temp file and initialise the schema."""
    test_db = tmp_path / "test_jobs.db"
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    db_module.init_db()
