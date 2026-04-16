"""Shared pytest fixtures for the linkedin-job-agent test suite."""
import pytest

from agent import db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a temp file and initialise a fresh schema for every test.

    This prevents tests from hitting (or creating) the real data/jobs.db and
    ensures the search_config + seen_jobs tables always exist.
    """
    test_db = tmp_path / "test_jobs.db"
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    yield
