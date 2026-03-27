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
