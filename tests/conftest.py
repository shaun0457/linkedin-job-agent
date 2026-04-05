"""Shared pytest fixtures for the linkedin-job-agent test suite."""
import pytest

import agent.db as db_module


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point DB_PATH at a per-test temp file and initialise a fresh schema.

    This ensures the search_config and seen_jobs tables always exist, even in
    tests that exercise run_pipeline() without explicitly mocking db calls.
    Tests that define their own ``isolated_db`` fixture (e.g. test_db.py)
    override this one within that module.
    """
    test_db = tmp_path / "test_jobs.db"
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    db_module.init_db()
