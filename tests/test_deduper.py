"""Tests for agent/deduper.py."""
from unittest.mock import patch

from agent.deduper import filter_new
from agent.models import Job


def _make_job(job_id: str, url: str) -> Job:
    return Job(
        job_id=job_id,
        title="ML Engineer",
        company="TestCo",
        location="Berlin",
        url=url,
        description="Test description.",
    )


def test_filter_new_all_new():
    jobs = [
        _make_job("id-1", "https://example.com/1"),
        _make_job("id-2", "https://example.com/2"),
    ]
    with patch("agent.deduper.db.is_seen", return_value=False):
        result = filter_new(jobs)
    assert result == jobs


def test_filter_new_all_seen():
    jobs = [
        _make_job("id-1", "https://example.com/1"),
        _make_job("id-2", "https://example.com/2"),
    ]
    with patch("agent.deduper.db.is_seen", return_value=True):
        result = filter_new(jobs)
    assert result == []


def test_filter_new_mixed():
    jobs = [
        _make_job("id-1", "https://example.com/1"),
        _make_job("id-2", "https://example.com/2"),
        _make_job("id-3", "https://example.com/3"),
    ]
    seen_ids = {"id-1", "id-2"}

    def mock_is_seen(job_id: str, url: str) -> bool:
        return job_id in seen_ids

    with patch("agent.deduper.db.is_seen", side_effect=mock_is_seen):
        result = filter_new(jobs)

    assert len(result) == 1
    assert result[0].job_id == "id-3"


def test_filter_new_empty_input():
    with patch("agent.deduper.db.is_seen", return_value=False):
        result = filter_new([])
    assert result == []


def test_filter_new_preserves_order():
    jobs = [_make_job(f"id-{i}", f"https://example.com/{i}") for i in range(5)]
    seen = {"id-1", "id-3"}

    def mock_is_seen(job_id: str, url: str) -> bool:
        return job_id in seen

    with patch("agent.deduper.db.is_seen", side_effect=mock_is_seen):
        result = filter_new(jobs)

    assert [j.job_id for j in result] == ["id-0", "id-2", "id-4"]
