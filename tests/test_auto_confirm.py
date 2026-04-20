"""Tests for P11: AUTO_CONFIRM mode in run_pipeline."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.models import Job, TailoredResult


# ── fixtures ─────────────────────────────────────────────────────────────────


def _make_job(job_id: str = "job-1", company: str = "DeepMind") -> Job:
    return Job(
        job_id=job_id,
        title="ML Engineer",
        company=company,
        location="London, UK",
        url=f"https://linkedin.com/jobs/view/{job_id}/",
        description="Build ML systems.",
    )


def _make_result(job: Job) -> TailoredResult:
    return TailoredResult(
        job=job,
        preview_data={"job_id": "rm-1", "resume_preview": {}, "improvements": [{"suggestion": "PyTorch"}]},
        rm_job_id="rm-1",
        master_resume_id="master-1",
        keywords_added=["PyTorch"],
    )


@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.apify_token = "mock"
    s.telegram_chat_id = "999"
    s.resume_matcher_url = "http://rm:8000"
    s.auto_confirm = False
    s.gemini_api_key = ""
    s.min_job_score = 5
    return s


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.bot = AsyncMock()
    app.bot.send_message = AsyncMock()
    return app


# ── test_auto_confirm_disabled_by_default ────────────────────────────────────


@pytest.mark.asyncio
async def test_auto_confirm_disabled_by_default(mock_app, mock_settings):
    """When auto_confirm is False, pipeline calls notify_job (not confirm_resume)."""
    from main import run_pipeline

    mock_settings.auto_confirm = False
    job = _make_job()
    result = _make_result(job)

    with (
        patch("main.get_search_config"),
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", return_value=[job]),
        patch("main.filter_new", return_value=[job]),
        patch("main.improver.tailor_resume", new=AsyncMock(return_value=result)),
        patch("main.db.insert_job"),
        patch("main.notifier.notify_job", new=AsyncMock()) as mock_notify,
        patch("main.improver.confirm_resume", new=AsyncMock()) as mock_confirm,
        patch("main.notifier.notify_run_summary", new=AsyncMock()),
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_notify.assert_awaited_once()
    mock_confirm.assert_not_awaited()


# ── test_auto_confirm_enabled_auto_confirms ──────────────────────────────────


@pytest.mark.asyncio
async def test_auto_confirm_enabled_auto_confirms(mock_app, mock_settings):
    """When auto_confirm is True and tailoring succeeds, pipeline calls confirm_resume."""
    from main import run_pipeline

    mock_settings.auto_confirm = True
    job = _make_job()
    result = _make_result(job)

    with (
        patch("main.get_search_config"),
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", return_value=[job]),
        patch("main.filter_new", return_value=[job]),
        patch("main.improver.tailor_resume", new=AsyncMock(return_value=result)),
        patch("main.db.insert_job"),
        patch("main.notifier.notify_job", new=AsyncMock()) as mock_notify,
        patch("main.improver.confirm_resume", new=AsyncMock(return_value="confirmed-1")) as mock_confirm,
        patch("main.notifier.notify_run_summary", new=AsyncMock()),
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_confirm.assert_awaited_once_with(
        "http://rm:8000",
        master_resume_id="master-1",
        preview_data=result.preview_data,
    )
    mock_notify.assert_not_awaited()


# ── test_auto_confirm_enabled_skips_on_failure ───────────────────────────────


@pytest.mark.asyncio
async def test_auto_confirm_enabled_skips_on_failure(mock_app, mock_settings):
    """When auto_confirm is True but tailoring fails, confirm_resume is not called."""
    from main import run_pipeline

    mock_settings.auto_confirm = True
    job = _make_job()

    with (
        patch("main.get_search_config"),
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", return_value=[job]),
        patch("main.filter_new", return_value=[job]),
        patch("main.improver.tailor_resume", new=AsyncMock(return_value=None)),
        patch("main.improver.confirm_resume", new=AsyncMock()) as mock_confirm,
        patch("main.notifier.notify_job", new=AsyncMock()) as mock_notify,
        patch("main.notifier.notify_run_summary", new=AsyncMock()) as mock_summary,
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_confirm.assert_not_awaited()
    mock_notify.assert_not_awaited()
    mock_summary.assert_awaited_once()
    assert mock_summary.call_args.kwargs["failed"] == 1
