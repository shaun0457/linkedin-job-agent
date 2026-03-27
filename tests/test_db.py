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


def test_insert_job_and_is_seen_by_job_id():
    db_module.insert_job(
        job_id="job-1",
        title="ML Engineer",
        company="DeepMind",
        url="https://example.com/job-1",
        preview_resume_id="preview-abc",
        notified_at=_now(),
    )
    assert db_module.is_seen("job-1", "https://other.com")


def test_insert_job_and_is_seen_by_url():
    db_module.insert_job(
        job_id="job-2",
        title="Data Scientist",
        company="Google",
        url="https://example.com/job-2",
        preview_resume_id="preview-def",
        notified_at=_now(),
    )
    assert db_module.is_seen("totally-different-id", "https://example.com/job-2")


def test_insert_job_duplicate_is_ignored():
    now = _now()
    db_module.insert_job(
        job_id="job-3",
        title="AI Engineer",
        company="OpenAI",
        url="https://example.com/job-3",
        preview_resume_id="preview-ghi",
        notified_at=now,
    )
    # Second insert should not raise (INSERT OR IGNORE)
    db_module.insert_job(
        job_id="job-3",
        title="AI Engineer",
        company="OpenAI",
        url="https://example.com/job-3",
        preview_resume_id="preview-ghi",
        notified_at=now,
    )
    stats = db_module.get_stats(since="2000-01-01T00:00:00")
    assert stats.get("notified", 0) == 1


def test_confirm_job():
    now = _now()
    db_module.insert_job(
        job_id="job-4",
        title="Research Scientist",
        company="Anthropic",
        url="https://example.com/job-4",
        preview_resume_id="preview-jkl",
        notified_at=now,
    )
    db_module.confirm_job("job-4", "confirmed-jkl", now)
    stats = db_module.get_stats(since="2000-01-01T00:00:00")
    assert stats.get("confirmed", 0) == 1
    assert stats.get("notified", 0) == 0


def test_skip_job():
    now = _now()
    db_module.insert_job(
        job_id="job-5",
        title="Platform Engineer",
        company="Stability AI",
        url="https://example.com/job-5",
        preview_resume_id="preview-mno",
        notified_at=now,
    )
    db_module.skip_job("job-5", now)
    stats = db_module.get_stats(since="2000-01-01T00:00:00")
    assert stats.get("skipped", 0) == 1
    assert stats.get("notified", 0) == 0


def test_get_stats_empty_for_future_date():
    db_module.insert_job(
        job_id="job-6",
        title="Engineer",
        company="Acme",
        url="https://example.com/job-6",
        preview_resume_id="preview-pqr",
        notified_at=_now(),
    )
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


def test_insert_job_with_confirm_payload():
    import json
    payload = json.dumps({"resume_id": "master-1", "job_id": "rm-1"})
    db_module.insert_job(
        job_id="job-cp",
        title="Engineer",
        company="Acme",
        url="https://example.com/job-cp",
        preview_resume_id="preview-cp",
        notified_at=_now(),
        confirm_payload=payload,
    )
    result = db_module.get_confirm_payload("job-cp")
    assert result == payload


def test_get_confirm_payload_missing():
    assert db_module.get_confirm_payload("nonexistent-job") is None


def test_insert_job_without_confirm_payload_defaults_to_none():
    db_module.insert_job(
        job_id="job-no-payload",
        title="Engineer",
        company="Acme",
        url="https://example.com/job-no-payload",
        preview_resume_id="preview-np",
        notified_at=_now(),
    )
    assert db_module.get_confirm_payload("job-no-payload") is None
