"""Integration tests for run_pipeline() in main.py — all external calls mocked."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

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


# ── happy path ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_happy_path_tailors_and_notifies(mock_app, mock_settings):
    """Full pipeline: 2 new jobs → 2 tailored → 2 notifications + 1 summary."""
    from main import run_pipeline

    jobs = [_make_job("job-1"), _make_job("job-2", "OpenAI")]
    results = [_make_result(j) for j in jobs]

    with (
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
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value=None)),
        patch("main.notifier.notify_error", new=AsyncMock()) as mock_error,
        patch("main.scrape_jobs_mock") as mock_scrape,
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_error.assert_awaited_once()
    mock_scrape.assert_not_called()


# ── no new jobs ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_no_new_jobs_expands_time_and_retries(mock_app, mock_settings):
    """When dedup returns 0, pipeline expands time range and retries scrape."""
    from main import run_pipeline

    job_new = _make_job("new-1")

    # First scrape (24h): all seen. Second scrape (1w): finds new job.
    with (
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", side_effect=[[_make_job()], [job_new]]) as mock_scrape,
        patch("main.filter_new", side_effect=[[], [job_new]]),
        patch("main.improver.tailor_resume", new=AsyncMock(return_value=_make_result(job_new))),
        patch("main.db.insert_job"),
        patch("main.notifier.notify_job", new=AsyncMock()) as mock_notify,
        patch("main.notifier.notify_run_summary", new=AsyncMock()) as mock_summary,
    ):
        await run_pipeline(mock_app, mock_settings)

    assert mock_scrape.call_count == 2
    mock_notify.assert_awaited_once()
    mock_summary.assert_awaited_once()


@pytest.mark.asyncio
async def test_pipeline_no_new_jobs_all_retries_exhausted(mock_app, mock_settings):
    """When all time ranges exhausted with 0 new jobs, sends empty notification."""
    from main import run_pipeline

    with (
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", return_value=[_make_job()]),
        patch("main.filter_new", return_value=[]),  # always 0
        patch("main.notifier.notify_run_summary", new=AsyncMock()) as mock_summary,
    ):
        await run_pipeline(mock_app, mock_settings)

    # Should send a summary with 0 found after exhausting retries
    mock_summary.assert_awaited_once()
    assert mock_summary.call_args.kwargs["found"] == 0


# ── partial failures ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_counts_failed_tailoring(mock_app, mock_settings):
    """Failed tailoring increments failed count in summary."""
    from main import run_pipeline

    job_ok = _make_job("ok")
    job_fail = _make_job("fail", "BadCorp")
    result_ok = _make_result(job_ok)

    with (
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


# ── AI scoring + tiered notifications ─────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_tiered_strong_gets_tailored_and_notified(mock_app, mock_settings):
    """Strong match (7+) gets tailored + individual notification."""
    from main import run_pipeline
    from agent.scorer import ScoredJob

    mock_settings.gemini_api_key = "fake-key"
    job = _make_job("strong", "NVIDIA")
    scored = [ScoredJob(job=job, score=9, reason="Top company")]

    with (
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", return_value=[job]),
        patch("main.filter_new", return_value=[job]),
        patch("main.score_jobs", new=AsyncMock(return_value=scored)),
        patch("main.improver.tailor_resume", new=AsyncMock(return_value=_make_result(job))) as mock_tailor,
        patch("main.db.insert_job"),
        patch("main.notifier.notify_job", new=AsyncMock()) as mock_notify,
        patch("main.notifier.notify_batch_summary", new=AsyncMock()) as mock_batch,
        patch("main.notifier.notify_run_summary", new=AsyncMock()),
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_tailor.assert_awaited_once()
    mock_notify.assert_awaited_once()
    assert mock_notify.call_args.kwargs["score"] == 9
    mock_batch.assert_not_awaited()


@pytest.mark.asyncio
async def test_pipeline_tiered_medium_gets_batch_summary(mock_app, mock_settings):
    """Medium match (4-6) gets batch summary, NOT individual notification."""
    from main import run_pipeline
    from agent.scorer import ScoredJob

    mock_settings.gemini_api_key = "fake-key"
    job = _make_job("med", "SAP")
    scored = [ScoredJob(job=job, score=5, reason="OK")]

    with (
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", return_value=[job]),
        patch("main.filter_new", return_value=[job]),
        patch("main.score_jobs", new=AsyncMock(return_value=scored)),
        patch("main.improver.tailor_resume", new=AsyncMock()) as mock_tailor,
        patch("main.db.insert_job") as mock_insert,
        patch("main.notifier.notify_job", new=AsyncMock()) as mock_notify,
        patch("main.notifier.notify_batch_summary", new=AsyncMock()) as mock_batch,
        patch("main.notifier.notify_run_summary", new=AsyncMock()),
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_tailor.assert_not_awaited()  # medium NOT tailored
    mock_notify.assert_not_awaited()  # no individual notify
    mock_batch.assert_awaited_once()  # batch summary sent


@pytest.mark.asyncio
async def test_pipeline_tiered_weak_stored_silently(mock_app, mock_settings):
    """Weak match (1-3) stored in DB, no notification."""
    from main import run_pipeline
    from agent.scorer import ScoredJob

    mock_settings.gemini_api_key = "fake-key"
    job = _make_job("weak", "NobodyCorp")
    scored = [ScoredJob(job=job, score=2, reason="Poor fit")]

    with (
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", return_value=[job]),
        patch("main.filter_new", return_value=[job]),
        patch("main.score_jobs", new=AsyncMock(return_value=scored)),
        patch("main.improver.tailor_resume", new=AsyncMock()) as mock_tailor,
        patch("main.db.insert_job") as mock_insert,
        patch("main.notifier.notify_job", new=AsyncMock()) as mock_notify,
        patch("main.notifier.notify_batch_summary", new=AsyncMock()) as mock_batch,
        patch("main.notifier.notify_run_summary", new=AsyncMock()),
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_tailor.assert_not_awaited()
    mock_notify.assert_not_awaited()
    mock_batch.assert_not_awaited()
    mock_insert.assert_called_once()  # stored in DB
    assert mock_insert.call_args.kwargs["status"] == "weak"


@pytest.mark.asyncio
async def test_pipeline_no_scoring_treats_all_as_strong(mock_app, mock_settings):
    """Without Gemini key, all jobs are tailored + notified (no tier split)."""
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
        patch("main.notifier.notify_job", new=AsyncMock()) as mock_notify,
        patch("main.notifier.notify_run_summary", new=AsyncMock()),
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_score.assert_not_awaited()
    mock_notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_pipeline_run_summary_includes_tier_breakdown(mock_app, mock_settings):
    """Run summary includes strong/medium/weak counts."""
    from main import run_pipeline
    from agent.scorer import ScoredJob

    mock_settings.gemini_api_key = "fake-key"
    j_strong = _make_job("s1", "NVIDIA")
    j_medium = _make_job("m1", "SAP")
    j_weak = _make_job("w1", "NobodyCorp")
    scored = [
        ScoredJob(job=j_strong, score=9, reason="Great"),
        ScoredJob(job=j_medium, score=5, reason="OK"),
        ScoredJob(job=j_weak, score=2, reason="Poor"),
    ]

    with (
        patch("main.improver.get_master_resume_id", new=AsyncMock(return_value="master-1")),
        patch("main.scrape_jobs_mock", return_value=[j_strong, j_medium, j_weak]),
        patch("main.filter_new", return_value=[j_strong, j_medium, j_weak]),
        patch("main.score_jobs", new=AsyncMock(return_value=scored)),
        patch("main.improver.tailor_resume", new=AsyncMock(return_value=_make_result(j_strong))),
        patch("main.db.insert_job"),
        patch("main.notifier.notify_job", new=AsyncMock()),
        patch("main.notifier.notify_batch_summary", new=AsyncMock()),
        patch("main.notifier.notify_run_summary", new=AsyncMock()) as mock_summary,
    ):
        await run_pipeline(mock_app, mock_settings)

    mock_summary.assert_awaited_once()
    kw = mock_summary.call_args.kwargs
    assert kw["strong"] == 1
    assert kw["medium"] == 1
    assert kw["weak"] == 1
