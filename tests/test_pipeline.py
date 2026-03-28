"""Integration tests for run_pipeline() in main.py — all external calls mocked."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from agent.models import Job, TailoredResult, SearchConfig


def _mock_search_config():
    return SearchConfig(
        keywords=["ML Engineer"],
        location="Berlin",
        experience_level=["MID_SENIOR_LEVEL"],
        blacklist_companies=[],
        max_jobs_per_run=10,
    )


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
    return s


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.bot = AsyncMock()
    app.bot.send_message = AsyncMock()
    return app


# ── happy path ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_happy_path_tailors_and_notifies(mock_app, mock_settings):
    """Full pipeline: 2 new jobs → 2 tailored → 2 notifications + 1 summary."""
    from main import run_pipeline

    jobs = [_make_job("job-1"), _make_job("job-2", "OpenAI")]
    results = [_make_result(j) for j in jobs]

    with (
        patch("main.get_search_config", return_value=_mock_search_config()),
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", return_value=jobs),
        patch("main.filter_new", return_value=jobs),
        patch("main.improver.tailor_resume", new=AsyncMock(side_effect=results)),
        patch("main.db.insert_job") as mock_insert,
        patch("main.notifier.notify_job", new=AsyncMock()) as mock_notify,
        patch("main.notifier.notify_run_summary", new=AsyncMock()) as mock_summary,
    ):
        await run_pipeline(mock_app, mock_settings)

    assert mock_insert.call_count == 2
    assert mock_notify.call_count == 2
    mock_summary.assert_awaited_once()
    summary_kwargs = mock_summary.call_args
    assert summary_kwargs.kwargs["found"] == 2
    assert summary_kwargs.kwargs["tailored"] == 2
    assert summary_kwargs.kwargs["failed"] == 0


@pytest.mark.asyncio
async def test_pipeline_insert_job_receives_correct_fields(mock_app, mock_settings):
    """insert_job must be called with preview_data, rm_job_id, master_resume_id."""
    from main import run_pipeline

    job = _make_job("job-x")
    result = _make_result(job)

    with (
        patch("main.get_search_config", return_value=_mock_search_config()),
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", return_value=[job]),
        patch("main.filter_new", return_value=[job]),
        patch("main.improver.tailor_resume", new=AsyncMock(return_value=result)),
        patch("main.db.insert_job") as mock_insert,
        patch("main.notifier.notify_job", new=AsyncMock()),
        patch("main.notifier.notify_run_summary", new=AsyncMock()),
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_insert.assert_called_once()
    call_kwargs = mock_insert.call_args.kwargs
    assert call_kwargs["job_id"] == "job-x"
    assert call_kwargs["preview_data"] == result.preview_data
    assert call_kwargs["rm_job_id"] == "rm-1"
    assert call_kwargs["master_resume_id"] == "master-1"


# ── no master resume ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_aborts_if_no_master_resume(mock_app, mock_settings):
    """Pipeline sends error and returns early if no master resume found."""
    from main import run_pipeline

    with (
        patch("main.get_search_config", return_value=_mock_search_config()),
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value=None)),
        patch("main.notifier.notify_error", new=AsyncMock()) as mock_error,
        patch("main.scrape_jobs_mock") as mock_scrape,
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_error.assert_awaited_once()
    mock_scrape.assert_not_called()


# ── no new jobs ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_no_new_jobs_sends_no_summary(mock_app, mock_settings):
    """When deduper filters out all jobs, no summary is sent."""
    from main import run_pipeline

    with (
        patch("main.get_search_config", return_value=_mock_search_config()),
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", return_value=[_make_job()]),
        patch("main.filter_new", return_value=[]),  # all seen
        patch("main.notifier.notify_run_summary", new=AsyncMock()) as mock_summary,
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_summary.assert_not_awaited()


# ── partial failures ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_counts_failed_tailoring(mock_app, mock_settings):
    """Failed tailoring increments failed count in summary."""
    from main import run_pipeline

    job_ok = _make_job("ok")
    job_fail = _make_job("fail", "BadCorp")
    result_ok = _make_result(job_ok)

    with (
        patch("main.get_search_config", return_value=_mock_search_config()),
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", return_value=[job_ok, job_fail]),
        patch("main.filter_new", return_value=[job_ok, job_fail]),
        patch(
            "main.improver.tailor_resume",
            new=AsyncMock(side_effect=[result_ok, None]),  # second fails
        ),
        patch("main.db.insert_job"),
        patch("main.notifier.notify_job", new=AsyncMock()),
        patch("main.notifier.notify_run_summary", new=AsyncMock()) as mock_summary,
    ):
        await run_pipeline(mock_app, mock_settings)

    summary_kwargs = mock_summary.call_args.kwargs
    assert summary_kwargs["found"] == 2
    assert summary_kwargs["tailored"] == 1
    assert summary_kwargs["failed"] == 1


# ── scraper failure ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_scraper_exception_sends_error(mock_app, mock_settings):
    """Scraper exception sends error notification and returns early."""
    from main import run_pipeline

    with (
        patch("main.get_search_config", return_value=_mock_search_config()),
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", side_effect=RuntimeError("Apify down")),
        patch("main.notifier.notify_error", new=AsyncMock()) as mock_error,
        patch("main.notifier.notify_run_summary", new=AsyncMock()) as mock_summary,
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_error.assert_awaited_once()
    mock_summary.assert_not_awaited()
