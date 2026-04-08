"""Shared pytest fixtures for the full test suite."""
import pytest
import agent.db as db_module


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a per-test temp file and initialise a fresh schema.

    This ensures every test starts with a clean, empty database and never
    touches the real data/jobs.db file.  Tests in test_db.py define their
    own ``isolated_db`` fixture that shadows this one for that module.
    """
    test_db = tmp_path / "test_jobs.db"
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    db_module.init_db()
