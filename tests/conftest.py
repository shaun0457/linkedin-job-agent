"""Shared pytest fixtures for the linkedin-job-agent test suite."""
import pytest
import agent.db as db_module


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point DB_PATH at a fresh temp file and initialise the schema for every test.

    This prevents any test from accidentally reading/writing the real jobs.db
    and fixes tests that call get_search_config() (which queries search_config).
    """
    test_db = tmp_path / "test_jobs.db"
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    db_module.init_db()
