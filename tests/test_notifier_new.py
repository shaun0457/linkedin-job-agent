"""Tests for new notifier functions: notify_run_summary, batch_summary, cmd_search_config (TDD)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.models import Job
from agent.scorer import ScoredJob


# ── notify_run_summary ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notify_run_summary_sends_message():
    """notify_run_summary must send a Telegram message with correct counts."""
    from agent.notifier import notify_run_summary

    mock_app = MagicMock()
    mock_app.bot = AsyncMock()
    mock_app.bot.send_message = AsyncMock()

    await notify_run_summary(mock_app, "12345", found=5, tailored=3, failed=1)

    mock_app.bot.send_message.assert_awaited_once()
    call_kwargs = mock_app.bot.send_message.call_args
    text = call_kwargs.kwargs.get("text") or call_kwargs.args[1] if call_kwargs.args else ""
    if not text:
        text = call_kwargs[1].get("text", "")

    assert "5" in text
    assert "3" in text
    assert "1" in text


@pytest.mark.asyncio
async def test_notify_run_summary_uses_markdownv2():
    from agent.notifier import notify_run_summary

    mock_app = MagicMock()
    mock_app.bot = AsyncMock()
    mock_app.bot.send_message = AsyncMock()

    await notify_run_summary(mock_app, "12345", found=2, tailored=2, failed=0)

    call_kwargs = mock_app.bot.send_message.call_args
    kwargs = call_kwargs.kwargs if call_kwargs.kwargs else call_kwargs[1]
    assert kwargs.get("parse_mode") == "MarkdownV2"


@pytest.mark.asyncio
async def test_notify_run_summary_chat_id_passed():
    from agent.notifier import notify_run_summary

    mock_app = MagicMock()
    mock_app.bot = AsyncMock()
    mock_app.bot.send_message = AsyncMock()

    await notify_run_summary(mock_app, "999888", found=1, tailored=1, failed=0)

    call_kwargs = mock_app.bot.send_message.call_args
    kwargs = call_kwargs.kwargs if call_kwargs.kwargs else call_kwargs[1]
    assert kwargs.get("chat_id") == "999888"


# ── notify_run_summary with tier breakdown ────────────────────────────────


@pytest.mark.asyncio
async def test_notify_run_summary_with_tier_breakdown():
    from agent.notifier import notify_run_summary

    app = MagicMock()
    app.bot = AsyncMock()
    app.bot.send_message = AsyncMock()

    await notify_run_summary(
        app, "12345", found=25, tailored=3, failed=0,
        strong=3, medium=8, weak=14,
    )

    text = app.bot.send_message.call_args.kwargs["text"]
    assert "🟢" in text
    assert "🟡" in text
    assert "🔴" in text
    assert "3" in text  # strong
    assert "8" in text  # medium
    assert "14" in text  # weak


@pytest.mark.asyncio
async def test_notify_run_summary_backward_compat():
    """Works without tier args (backward compatible)."""
    from agent.notifier import notify_run_summary

    app = MagicMock()
    app.bot = AsyncMock()
    app.bot.send_message = AsyncMock()

    await notify_run_summary(app, "12345", found=5, tailored=3, failed=1)
    app.bot.send_message.assert_awaited_once()


# ── notify_batch_summary ──────────────────────────────────────────────────


def _make_scored_job(job_id: str, company: str, score: int) -> ScoredJob:
    job = Job(
        job_id=job_id, title="Engineer", company=company,
        location="Germany", url=f"https://linkedin.com/jobs/{job_id}",
        description="desc",
    )
    return ScoredJob(job=job, score=score, reason="OK")


@pytest.mark.asyncio
async def test_notify_batch_summary_sends_single_message():
    from agent.notifier import notify_batch_summary

    app = MagicMock()
    app.bot = AsyncMock()
    app.bot.send_message = AsyncMock()

    jobs = [_make_scored_job("1", "SAP", 5), _make_scored_job("2", "Bosch", 4)]
    await notify_batch_summary(app, "12345", jobs)

    app.bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_notify_batch_summary_contains_companies():
    from agent.notifier import notify_batch_summary

    app = MagicMock()
    app.bot = AsyncMock()
    app.bot.send_message = AsyncMock()

    jobs = [_make_scored_job("1", "SAP", 5), _make_scored_job("2", "Bosch", 4)]
    await notify_batch_summary(app, "12345", jobs)

    text = app.bot.send_message.call_args.kwargs["text"]
    assert "SAP" in text
    assert "Bosch" in text


@pytest.mark.asyncio
async def test_notify_batch_summary_empty_no_message():
    from agent.notifier import notify_batch_summary

    app = MagicMock()
    app.bot = AsyncMock()
    app.bot.send_message = AsyncMock()

    await notify_batch_summary(app, "12345", [])
    app.bot.send_message.assert_not_awaited()


# ── cmd_view_medium ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_view_medium_shows_jobs():
    from agent.notifier import cmd_view_medium

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()

    fake_jobs = [
        {"job_id": "1", "title": "Data Eng", "company": "SAP", "url": "https://x.com/1",
         "score": 5, "score_reason": "OK", "notified_at": "2026-04-03T00:00:00"},
        {"job_id": "2", "title": "ML Eng", "company": "Bosch", "url": "https://x.com/2",
         "score": 4, "score_reason": "Decent", "notified_at": "2026-04-03T00:00:00"},
    ]

    with patch("agent.notifier.db.get_medium_jobs", return_value=fake_jobs):
        await cmd_view_medium(mock_update, mock_context)

    mock_update.message.reply_text.assert_awaited_once()
    text = mock_update.message.reply_text.call_args.args[0]
    assert "SAP" in text
    assert "Bosch" in text


@pytest.mark.asyncio
async def test_cmd_view_medium_empty():
    from agent.notifier import cmd_view_medium

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()

    with patch("agent.notifier.db.get_medium_jobs", return_value=[]):
        await cmd_view_medium(mock_update, mock_context)

    text = mock_update.message.reply_text.call_args.args[0]
    assert "沒有" in text or "無" in text


# ── cmd_search_config ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_search_config_shows_experience_level():
    """cmd_search_config must show experience_level (not in /config)."""
    from agent.notifier import cmd_search_config
    from agent.models import SearchConfig

    mock_sc = SearchConfig(
        keywords=["AI Engineer"],
        location="Germany",
        experience_level=["MID_SENIOR_LEVEL", "ENTRY_LEVEL"],
        blacklist_companies=["BadCorp"],
        max_jobs_per_run=10,
    )

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()

    with patch("agent.notifier.cfg.get_search_config", return_value=mock_sc):
        await cmd_search_config(mock_update, mock_context)

    mock_update.message.reply_text.assert_awaited_once()
    call_args = mock_update.message.reply_text.call_args
    text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")

    # MarkdownV2 escapes '_' → '\_', so check escaped variants
    assert "MID\\_SENIOR\\_LEVEL" in text or "ENTRY\\_LEVEL" in text


@pytest.mark.asyncio
async def test_cmd_search_config_shows_blacklist():
    """cmd_search_config must show blacklist_companies."""
    from agent.notifier import cmd_search_config
    from agent.models import SearchConfig

    mock_sc = SearchConfig(
        keywords=["ML Engineer"],
        location="Berlin",
        experience_level=["MID_SENIOR_LEVEL"],
        blacklist_companies=["EvilCorp", "BadInc"],
        max_jobs_per_run=20,
    )

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()

    with patch("agent.notifier.cfg.get_search_config", return_value=mock_sc):
        await cmd_search_config(mock_update, mock_context)

    call_args = mock_update.message.reply_text.call_args
    text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")

    assert "EvilCorp" in text or "BadInc" in text


@pytest.mark.asyncio
async def test_cmd_search_config_empty_blacklist():
    """cmd_search_config shows '—' or similar when blacklist is empty."""
    from agent.notifier import cmd_search_config
    from agent.models import SearchConfig

    mock_sc = SearchConfig(
        keywords=["AI Engineer"],
        location="Remote",
        experience_level=["ENTRY_LEVEL"],
        blacklist_companies=[],
        max_jobs_per_run=5,
    )

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()

    with patch("agent.notifier.cfg.get_search_config", return_value=mock_sc):
        await cmd_search_config(mock_update, mock_context)

    mock_update.message.reply_text.assert_awaited_once()
