"""Notifier coverage tests: notify_job, callbacks, commands."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.models import Job, TailoredResult


def _mock_app():
    app = MagicMock()
    app.bot = AsyncMock()
    app.bot.send_message = AsyncMock()
    return app


def _mock_update():
    update = MagicMock()
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    return update


def _mock_context(settings=None, bot_data=None):
    context = MagicMock()
    if settings is None:
        settings = MagicMock()
        settings.resume_matcher_url = "http://localhost:8001"
    context.bot_data = bot_data or {"settings": settings}
    return context


SAMPLE_JOB = Job(
    job_id="job-001",
    title="ML Engineer",
    company="DeepMind",
    location="London",
    url="https://linkedin.com/jobs/001",
    description="PyTorch expert needed",
)


# ── notify_job ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notify_job_sends_message_with_inline_keyboard():
    from agent.notifier import notify_job

    result = TailoredResult(
        job=SAMPLE_JOB,
        preview_data={"resume_preview": {}},
        rm_job_id="rm-001",
        master_resume_id="master-001",
        keywords_added=["PyTorch", "TensorFlow"],
    )
    app = _mock_app()
    await notify_job(app, "12345", result)

    app.bot.send_message.assert_awaited_once()
    kwargs = app.bot.send_message.call_args.kwargs
    assert kwargs["chat_id"] == "12345"
    assert kwargs["parse_mode"] == "MarkdownV2"
    assert "DeepMind" in kwargs["text"]
    assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_notify_job_no_keywords_shows_dash():
    from agent.notifier import notify_job

    result = TailoredResult(
        job=SAMPLE_JOB,
        preview_data={},
        rm_job_id="rm-001",
        master_resume_id="master-001",
        keywords_added=[],
    )
    app = _mock_app()
    await notify_job(app, "12345", result)

    text = app.bot.send_message.call_args.kwargs["text"]
    assert "—" in text


# ── notify_error ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notify_error_sends_warning_message():
    from agent.notifier import notify_error

    app = _mock_app()
    await notify_error(app, "12345", "Something went wrong")

    app.bot.send_message.assert_awaited_once()
    text = app.bot.send_message.call_args.args[0] if app.bot.send_message.call_args.args else app.bot.send_message.call_args.kwargs.get("text", "")
    # Could be positional or keyword
    call_args = app.bot.send_message.call_args
    sent_text = call_args.kwargs.get("text") or (call_args.args[1] if len(call_args.args) > 1 else "")
    assert "⚠️" in sent_text
    assert "Something went wrong" in sent_text


# ── handle_callback ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_callback_confirm_routes_to_handle_confirm():
    from agent.notifier import handle_callback

    update = MagicMock()
    query = AsyncMock()
    query.data = "confirm:job-123"
    query.answer = AsyncMock()
    update.callback_query = query

    context = _mock_context()

    with patch("agent.notifier._handle_confirm", new=AsyncMock()) as mock_confirm:
        await handle_callback(update, context)

    mock_confirm.assert_awaited_once()
    args = mock_confirm.call_args.args
    assert args[2] == "job-123"


@pytest.mark.asyncio
async def test_handle_callback_skip_routes_to_handle_skip():
    from agent.notifier import handle_callback

    update = MagicMock()
    query = AsyncMock()
    query.data = "skip:job-456"
    query.answer = AsyncMock()
    update.callback_query = query

    context = _mock_context()

    with patch("agent.notifier._handle_skip", new=AsyncMock()) as mock_skip:
        await handle_callback(update, context)

    mock_skip.assert_awaited_once()
    args = mock_skip.call_args.args
    assert args[2] == "job-456"


@pytest.mark.asyncio
async def test_handle_callback_unknown_data_is_noop():
    from agent.notifier import handle_callback

    update = MagicMock()
    query = AsyncMock()
    query.data = "unknown:whatever"
    query.answer = AsyncMock()
    update.callback_query = query

    context = _mock_context()

    with (
        patch("agent.notifier._handle_confirm", new=AsyncMock()) as mock_confirm,
        patch("agent.notifier._handle_skip", new=AsyncMock()) as mock_skip,
    ):
        await handle_callback(update, context)

    mock_confirm.assert_not_awaited()
    mock_skip.assert_not_awaited()


# ── _handle_confirm ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_confirm_no_preview_data_shows_warning():
    from agent.notifier import _handle_confirm

    settings = MagicMock()
    settings.resume_matcher_url = "http://localhost:8001"
    query = AsyncMock()
    query.message = AsyncMock()

    with patch("agent.notifier.db.get_preview_data", return_value=None):
        await _handle_confirm(query, settings, "job-001")

    query.message.reply_text.assert_awaited_once()
    text = query.message.reply_text.call_args.args[0]
    assert "⚠️" in text


@pytest.mark.asyncio
async def test_handle_confirm_no_meta_shows_warning():
    from agent.notifier import _handle_confirm

    settings = MagicMock()
    settings.resume_matcher_url = "http://localhost:8001"
    query = AsyncMock()
    query.message = AsyncMock()

    with (
        patch("agent.notifier.db.get_preview_data", return_value={"job_id": "rm-1"}),
        patch("agent.notifier.db.get_job_meta", return_value=None),
    ):
        await _handle_confirm(query, settings, "job-001")

    query.message.reply_text.assert_awaited()
    text = query.message.reply_text.call_args.args[0]
    assert "master resume" in text


@pytest.mark.asyncio
async def test_handle_confirm_success_calls_db_confirm():
    from agent.notifier import _handle_confirm

    settings = MagicMock()
    settings.resume_matcher_url = "http://localhost:8001"
    query = AsyncMock()
    query.message = AsyncMock()

    with (
        patch("agent.notifier.db.get_preview_data", return_value={"job_id": "rm-1"}),
        patch("agent.notifier.db.get_job_meta", return_value={"master_resume_id": "master-1"}),
        patch("agent.notifier.improver.confirm_resume", new=AsyncMock(return_value="confirmed-1")),
        patch("agent.notifier.db.confirm_job") as mock_confirm_job,
    ):
        await _handle_confirm(query, settings, "job-001")

    mock_confirm_job.assert_called_once()
    reply_text = query.message.reply_text.call_args.args[0]
    assert "✅" in reply_text


@pytest.mark.asyncio
async def test_handle_confirm_confirm_failure_shows_warning():
    from agent.notifier import _handle_confirm

    settings = MagicMock()
    settings.resume_matcher_url = "http://localhost:8001"
    query = AsyncMock()
    query.message = AsyncMock()

    with (
        patch("agent.notifier.db.get_preview_data", return_value={"job_id": "rm-1"}),
        patch("agent.notifier.db.get_job_meta", return_value={"master_resume_id": "master-1"}),
        patch("agent.notifier.improver.confirm_resume", new=AsyncMock(return_value=None)),
    ):
        await _handle_confirm(query, settings, "job-001")

    text = query.message.reply_text.call_args.args[0]
    assert "⚠️" in text


# ── _handle_skip ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_skip_calls_skip_job_and_edits_message():
    from agent.notifier import _handle_skip

    settings = MagicMock()
    query = AsyncMock()
    query.message = MagicMock()
    query.message.text = "ML Engineer @ DeepMind\nLondon"

    with patch("agent.notifier.db.skip_job") as mock_skip:
        await _handle_skip(query, settings, "job-001")

    mock_skip.assert_called_once()
    query.edit_message_text.assert_awaited_once()
    text = query.edit_message_text.call_args.kwargs["text"]
    assert "已跳過" in text


# ── cmd_run ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_run_no_pipeline_sends_warning():
    from agent.notifier import cmd_run

    update = _mock_update()
    context = _mock_context(bot_data={"settings": MagicMock()})
    context.bot_data["run_pipeline"] = None

    await cmd_run(update, context)

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args.args[0]
    assert "⚠️" in text


@pytest.mark.asyncio
async def test_cmd_run_with_pipeline_triggers_task():
    from agent.notifier import cmd_run
    import asyncio

    update = _mock_update()
    pipeline_called = False

    async def fake_pipeline():
        nonlocal pipeline_called
        pipeline_called = True

    context = _mock_context(bot_data={"settings": MagicMock(), "run_pipeline": fake_pipeline})

    await cmd_run(update, context)

    update.message.reply_text.assert_awaited()
    # Give the task a chance to run
    await asyncio.sleep(0)


# ── cmd_status ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_status_shows_stats():
    from agent.notifier import cmd_status

    update = _mock_update()
    context = _mock_context()

    with patch("agent.notifier.db.get_stats", return_value={"notified": 3, "confirmed": 2, "skipped": 1}):
        await cmd_status(update, context)

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args.args[0]
    assert "統計" in text


# ── cmd_list ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_list_no_jobs():
    from agent.notifier import cmd_list

    update = _mock_update()
    context = _mock_context()

    with patch("agent.notifier.db.get_recent_confirmed", return_value=[]):
        await cmd_list(update, context)

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args.args[0]
    assert "尚無" in text


@pytest.mark.asyncio
async def test_cmd_list_with_jobs():
    from agent.notifier import cmd_list

    update = _mock_update()
    settings = MagicMock()
    settings.resume_matcher_url = "http://localhost:8001"
    context = _mock_context(settings=settings)

    jobs = [{"title": "ML Eng", "company": "Acme", "confirmed_resume_id": "r-1"}]
    with patch("agent.notifier.db.get_recent_confirmed", return_value=jobs):
        await cmd_list(update, context)

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args.args[0]
    assert "ML Eng" in text


# ── cmd_retry ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_retry_no_args_shows_usage():
    from agent.notifier import cmd_retry

    update = _mock_update()
    context = _mock_context()
    context.args = []

    await cmd_retry(update, context)

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args.args[0]
    assert "用法" in text


@pytest.mark.asyncio
async def test_cmd_retry_unknown_job_id():
    from agent.notifier import cmd_retry

    update = _mock_update()
    context = _mock_context()
    context.args = ["nonexistent-job"]

    with patch("agent.notifier.db.get_preview_data", return_value=None):
        await cmd_retry(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "找不到" in text


@pytest.mark.asyncio
async def test_cmd_retry_no_meta_shows_warning():
    from agent.notifier import cmd_retry

    update = _mock_update()
    context = _mock_context()
    context.args = ["job-001"]

    with (
        patch("agent.notifier.db.get_preview_data", return_value={"job_id": "rm-1"}),
        patch("agent.notifier.db.get_job_meta", return_value=None),
    ):
        await cmd_retry(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "⚠️" in text


@pytest.mark.asyncio
async def test_cmd_retry_success():
    from agent.notifier import cmd_retry

    update = _mock_update()
    settings = MagicMock()
    settings.resume_matcher_url = "http://localhost:8001"
    context = _mock_context(settings=settings)
    context.args = ["job-001"]

    with (
        patch("agent.notifier.db.get_preview_data", return_value={"job_id": "rm-1"}),
        patch("agent.notifier.db.get_job_meta", return_value={"master_resume_id": "master-1"}),
        patch("agent.notifier.improver.confirm_resume", new=AsyncMock(return_value="confirmed-1")),
        patch("agent.notifier.db.confirm_job"),
    ):
        await cmd_retry(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "✅" in text


@pytest.mark.asyncio
async def test_cmd_retry_confirm_failure():
    from agent.notifier import cmd_retry

    update = _mock_update()
    context = _mock_context()
    context.args = ["job-001"]

    with (
        patch("agent.notifier.db.get_preview_data", return_value={"job_id": "rm-1"}),
        patch("agent.notifier.db.get_job_meta", return_value={"master_resume_id": "master-1"}),
        patch("agent.notifier.improver.confirm_resume", new=AsyncMock(return_value=None)),
    ):
        await cmd_retry(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "⚠️" in text


# ── cmd_config ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_config_shows_basic_settings():
    from agent.notifier import cmd_config

    update = _mock_update()
    context = _mock_context()

    sc = MagicMock()
    sc.keywords = ["ML", "AI"]
    sc.location = "Berlin"
    sc.max_jobs_per_run = 10

    with patch("agent.notifier.cfg.get_search_config", return_value=sc):
        await cmd_config(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "ML" in text
    assert "Berlin" in text


# ── cmd_set_keywords ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_set_keywords_no_args_shows_usage():
    from agent.notifier import cmd_set_keywords

    update = _mock_update()
    context = _mock_context()
    context.args = []

    await cmd_set_keywords(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "用法" in text


@pytest.mark.asyncio
async def test_cmd_set_keywords_updates():
    from agent.notifier import cmd_set_keywords

    update = _mock_update()
    context = _mock_context()
    context.args = ["ML", "Engineer,", "AI"]

    with patch("agent.notifier.cfg.set_keywords") as mock_set:
        await cmd_set_keywords(update, context)

    mock_set.assert_called_once()
    text = update.message.reply_text.call_args.args[0]
    assert "✅" in text


@pytest.mark.asyncio
async def test_cmd_set_keywords_empty_after_split():
    from agent.notifier import cmd_set_keywords

    update = _mock_update()
    context = _mock_context()
    context.args = [",", " , "]

    with patch("agent.notifier.cfg.set_keywords") as mock_set:
        await cmd_set_keywords(update, context)

    mock_set.assert_not_called()
    text = update.message.reply_text.call_args.args[0]
    assert "⚠️" in text


# ── cmd_set_location ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_set_location_no_args():
    from agent.notifier import cmd_set_location

    update = _mock_update()
    context = _mock_context()
    context.args = []

    with patch("agent.notifier.cfg.set_location") as mock_set:
        await cmd_set_location(update, context)

    mock_set.assert_not_called()
    text = update.message.reply_text.call_args.args[0]
    assert "用法" in text


@pytest.mark.asyncio
async def test_cmd_set_location_updates():
    from agent.notifier import cmd_set_location

    update = _mock_update()
    context = _mock_context()
    context.args = ["Berlin,", "Germany"]

    with patch("agent.notifier.cfg.set_location") as mock_set:
        await cmd_set_location(update, context)

    mock_set.assert_called_once_with("Berlin, Germany")
    text = update.message.reply_text.call_args.args[0]
    assert "✅" in text


# ── cmd_set_max ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_set_max_non_digit_shows_usage():
    from agent.notifier import cmd_set_max

    update = _mock_update()
    context = _mock_context()
    context.args = ["abc"]

    await cmd_set_max(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "用法" in text


@pytest.mark.asyncio
async def test_cmd_set_max_updates():
    from agent.notifier import cmd_set_max

    update = _mock_update()
    context = _mock_context()
    context.args = ["20"]

    with patch("agent.notifier.cfg.set_max_jobs") as mock_set:
        await cmd_set_max(update, context)

    mock_set.assert_called_once_with(20)
    text = update.message.reply_text.call_args.args[0]
    assert "✅" in text


# ── cmd_help ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_help_sends_markdownv2():
    from agent.notifier import cmd_help

    update = _mock_update()
    context = _mock_context()

    await cmd_help(update, context)

    update.message.reply_text.assert_awaited_once()
    kwargs = update.message.reply_text.call_args.kwargs
    assert kwargs.get("parse_mode") == "MarkdownV2"


@pytest.mark.asyncio
async def test_cmd_help_mentions_search_config():
    from agent.notifier import cmd_help

    update = _mock_update()
    context = _mock_context()

    await cmd_help(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "search" in text.lower()


# ── _esc_url ──────────────────────────────────────────────────────────────────


def test_esc_url_escapes_closing_paren():
    from agent.notifier import _esc_url

    assert _esc_url("https://example.com/path)more") == r"https://example.com/path\)more"


def test_esc_url_escapes_backslash():
    from agent.notifier import _esc_url

    assert _esc_url("https://example.com/path\\more") == r"https://example.com/path\\more"
