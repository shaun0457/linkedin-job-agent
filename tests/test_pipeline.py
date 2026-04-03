"""Integration tests for run_pipeline() in main.py — all external calls mocked."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from agent.models import Job, TailoredResult


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
    s.gemini_api_key = ""
    s.min_job_score = 5
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


# ── real scraper path (non-mock token) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_uses_real_scraper_when_token_is_real(mock_app, mock_settings):
    """When apify_token is a real token (not 'mock'), pipeline calls scrape_jobs."""
    from main import run_pipeline

    mock_settings.apify_token = "apify_api_REAL_TOKEN"
    job = _make_job()

    with (
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs", return_value=[job]) as mock_real_scrape,
        patch("main.scrape_jobs_mock") as mock_mock_scrape,
        patch("main.filter_new", return_value=[job]),
        patch("main.improver.tailor_resume", new=AsyncMock(return_value=_make_result(job))),
        patch("main.db.insert_job"),
        patch("main.notifier.notify_job", new=AsyncMock()),
        patch("main.notifier.notify_run_summary", new=AsyncMock()),
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_real_scrape.assert_called_once()
    mock_mock_scrape.assert_not_called()


# ── AI scoring integration ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_with_scoring_filters_low_quality_jobs(mock_app, mock_settings):
    """When gemini_api_key is set, scoring filters out low-score jobs."""
    from main import run_pipeline
    from agent.scorer import ScoredJob

    mock_settings.gemini_api_key = "fake-gemini-key"
    mock_settings.min_job_score = 5

    job_good = _make_job("good", "NVIDIA")
    job_bad = _make_job("bad", "NobodyCorp")

    scored_result = [ScoredJob(job=job_good, score=9, reason="Top company")]

    with (
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", return_value=[job_good, job_bad]),
        patch("main.filter_new", return_value=[job_good, job_bad]),
        patch("main.score_jobs", new=AsyncMock(return_value=scored_result)) as mock_score,
        patch("main.improver.tailor_resume", new=AsyncMock(return_value=_make_result(job_good))),
        patch("main.db.insert_job"),
        patch("main.notifier.notify_job", new=AsyncMock()) as mock_notify,
        patch("main.notifier.notify_run_summary", new=AsyncMock()) as mock_summary,
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_score.assert_awaited_once()
    assert mock_notify.call_count == 1  # only good job notified
    summary_kwargs = mock_summary.call_args.kwargs
    assert summary_kwargs["found"] == 1  # only scored jobs counted
    assert summary_kwargs["tailored"] == 1


@pytest.mark.asyncio
async def test_pipeline_scoring_filters_all_jobs_returns_early(mock_app, mock_settings):
    """When scoring filters out ALL jobs, pipeline returns without tailoring."""
    from main import run_pipeline

    mock_settings.gemini_api_key = "fake-gemini-key"
    mock_settings.min_job_score = 8

    job = _make_job()

    with (
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", return_value=[job]),
        patch("main.filter_new", return_value=[job]),
        patch("main.score_jobs", new=AsyncMock(return_value=[])),  # all filtered
        patch("main.improver.tailor_resume", new=AsyncMock()) as mock_tailor,
        patch("main.notifier.notify_run_summary", new=AsyncMock()) as mock_summary,
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_tailor.assert_not_awaited()
    mock_summary.assert_not_awaited()


@pytest.mark.asyncio
async def test_pipeline_skips_scoring_without_gemini_key(mock_app, mock_settings):
    """When gemini_api_key is empty, scoring is skipped entirely."""
    from main import run_pipeline

    mock_settings.gemini_api_key = ""
    job = _make_job()

    with (
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", return_value=[job]),
        patch("main.filter_new", return_value=[job]),
        patch("main.score_jobs", new=AsyncMock()) as mock_score,
        patch("main.improver.tailor_resume", new=AsyncMock(return_value=_make_result(job))),
        patch("main.db.insert_job"),
        patch("main.notifier.notify_job", new=AsyncMock()),
        patch("main.notifier.notify_run_summary", new=AsyncMock()),
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_score.assert_not_awaited()
