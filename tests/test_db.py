"""Tests for agent/db.py using a temporary SQLite file."""
from datetime import datetime, timezone

import pytest

import agent.db as db_module


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point DB_PATH at a temp file and initialise a fresh schema for each test."""
    test_db = tmp_path / "test_jobs.db"
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    db_module.init_db()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_init_db_creates_file(tmp_path, monkeypatch):
    db_path = tmp_path / "fresh.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()
    assert db_path.exists()


def test_is_seen_returns_false_for_unknown_job():
    assert not db_module.is_seen("unknown-id", "https://example.com/unknown")


def _insert(job_id: str, title: str = "Engineer", company: str = "Acme", url: str = None) -> None:
    db_module.insert_job(
        job_id=job_id,
        title=title,
        company=company,
        url=url or f"https://example.com/{job_id}",
        preview_data={"job_id": "rm-1", "resume_preview": {}, "improvements": []},
        rm_job_id="rm-1",
        master_resume_id="master-1",
        notified_at=_now(),
    )


def test_insert_job_and_is_seen_by_job_id():
    _insert("job-1", title="ML Engineer", company="DeepMind")
    assert db_module.is_seen("job-1", "https://other.com")


def test_insert_job_and_is_seen_by_url():
    _insert("job-2", title="Data Scientist", company="Google")
    assert db_module.is_seen("totally-different-id", "https://example.com/job-2")


def test_insert_job_duplicate_is_ignored():
    _insert("job-3", title="AI Engineer", company="OpenAI")
    # Second insert should not raise (INSERT OR IGNORE)
    _insert("job-3", title="AI Engineer", company="OpenAI")
    stats = db_module.get_stats(since="2000-01-01T00:00:00")
    assert stats.get("notified", 0) == 1


def test_confirm_job():
    now = _now()
    _insert("job-4", title="Research Scientist", company="Anthropic")
    db_module.confirm_job("job-4", "confirmed-jkl", now)
    stats = db_module.get_stats(since="2000-01-01T00:00:00")
    assert stats.get("confirmed", 0) == 1
    assert stats.get("notified", 0) == 0


def test_skip_job():
    now = _now()
    _insert("job-5", title="Platform Engineer", company="Stability AI")
    db_module.skip_job("job-5", now)
    stats = db_module.get_stats(since="2000-01-01T00:00:00")
    assert stats.get("skipped", 0) == 1
    assert stats.get("notified", 0) == 0


def test_get_stats_empty_for_future_date():
    _insert("job-6")
    stats = db_module.get_stats(since="2099-01-01T00:00:00")
    assert stats == {}


def test_set_and_get_config_value():
    db_module.set_config_value("location", '"London"')
    assert db_module.get_config_value("location") == '"London"'


def test_set_config_value_overwrite():
    db_module.set_config_value("location", '"Berlin"')
    db_module.set_config_value("location", '"Munich"')
    assert db_module.get_config_value("location") == '"Munich"'


def test_get_config_value_missing_key():
    assert db_module.get_config_value("nonexistent_key") is None


def test_get_search_overrides_empty_when_no_config():
    overrides = db_module.get_search_overrides()
    assert overrides == {}


def test_get_search_overrides_returns_decoded_values():
    import json
    db_module.set_config_value("location", json.dumps("Berlin"))
    db_module.set_config_value("max_jobs_per_run", json.dumps(10))
    overrides = db_module.get_search_overrides()
    assert overrides["location"] == "Berlin"
    assert overrides["max_jobs_per_run"] == 10
