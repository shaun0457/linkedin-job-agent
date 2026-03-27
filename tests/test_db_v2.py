"""Tests for new DB fields: preview_data, rm_job_id (TDD)."""
import json
import pytest
from pathlib import Path
from agent import db


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


PREVIEW_DATA = {
    "request_id": "req-123",
    "resume_id": None,
    "job_id": "rm-job-xyz",
    "resume_preview": {"personalInfo": {"name": "Test"}},
    "improvements": [{"suggestion": "Added PyTorch", "lineNumber": 1}],
    "warnings": [],
    "refinement_attempted": False,
    "refinement_successful": False,
}


def test_insert_job_stores_preview_data():
    """insert_job must accept and store preview_data as JSON."""
    db.insert_job(
        job_id="job-1",
        title="ML Engineer",
        company="DeepMind",
        url="https://linkedin.com/1",
        preview_data=PREVIEW_DATA,
        rm_job_id="rm-job-xyz",
        master_resume_id="master-abc",
        notified_at="2026-01-01T00:00:00",
    )

    data = db.get_preview_data("job-1")
    assert data is not None
    assert data["request_id"] == "req-123"
    assert data["job_id"] == "rm-job-xyz"
    assert data["improvements"][0]["suggestion"] == "Added PyTorch"


def test_get_preview_data_returns_none_for_unknown():
    result = db.get_preview_data("nonexistent")
    assert result is None


def test_insert_job_stores_rm_job_id_and_master_resume_id():
    db.insert_job(
        job_id="job-2",
        title="Data Scientist",
        company="OpenAI",
        url="https://linkedin.com/2",
        preview_data=PREVIEW_DATA,
        rm_job_id="rm-job-abc",
        master_resume_id="master-xyz",
        notified_at="2026-01-01T00:00:00",
    )

    meta = db.get_job_meta("job-2")
    assert meta is not None
    assert meta["rm_job_id"] == "rm-job-abc"
    assert meta["master_resume_id"] == "master-xyz"


def test_skip_job_clears_preview_data():
    db.insert_job(
        job_id="job-3",
        title="AI Engineer",
        company="Anthropic",
        url="https://linkedin.com/3",
        preview_data=PREVIEW_DATA,
        rm_job_id="rm-job-123",
        master_resume_id="master-abc",
        notified_at="2026-01-01T00:00:00",
    )

    db.skip_job("job-3", "2026-01-02T00:00:00")
    data = db.get_preview_data("job-3")
    assert data is None


def test_confirm_job_sets_status_and_resume_id():
    db.insert_job(
        job_id="job-4",
        title="ML Researcher",
        company="Meta",
        url="https://linkedin.com/4",
        preview_data=PREVIEW_DATA,
        rm_job_id="rm-job-456",
        master_resume_id="master-abc",
        notified_at="2026-01-01T00:00:00",
    )

    db.confirm_job("job-4", "resume-confirmed-789", "2026-01-02T00:00:00")
    confirmed = db.get_recent_confirmed(limit=1)
    assert len(confirmed) == 1
    assert confirmed[0]["confirmed_resume_id"] == "resume-confirmed-789"


def _insert(job_id: str, notified_at: str = "2026-01-01T08:00:00") -> None:
    db.insert_job(
        job_id=job_id,
        title="ML Engineer",
        company="Acme",
        url=f"https://example.com/{job_id}",
        preview_data=PREVIEW_DATA,
        rm_job_id="rm-1",
        master_resume_id="master-1",
        notified_at=notified_at,
    )


def test_get_pending_jobs_returns_notified_only():
    """get_pending_jobs returns only jobs with status='notified'."""
    _insert("pending-1")
    _insert("pending-2")
    _insert("confirmed-1")
    db.confirm_job("confirmed-1", "res-1", "2026-01-01T09:00:00")

    pending = db.get_pending_jobs()
    ids = {j["job_id"] for j in pending}
    assert "pending-1" in ids
    assert "pending-2" in ids
    assert "confirmed-1" not in ids


def test_get_pending_jobs_respects_limit():
    for i in range(5):
        _insert(f"pj-{i}", notified_at=f"2026-01-0{i+1}T00:00:00")

    result = db.get_pending_jobs(limit=2)
    assert len(result) == 2


def test_get_pending_jobs_returns_newest_first():
    _insert("old-job", notified_at="2026-01-01T08:00:00")
    _insert("new-job", notified_at="2026-01-10T08:00:00")

    pending = db.get_pending_jobs()
    assert pending[0]["job_id"] == "new-job"
    assert pending[1]["job_id"] == "old-job"


def test_get_pending_jobs_empty_when_all_decided():
    _insert("j1")
    db.skip_job("j1", "2026-01-01T09:00:00")

    assert db.get_pending_jobs() == []
