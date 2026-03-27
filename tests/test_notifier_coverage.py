"""Broad coverage tests for agent/notifier.py — notify_job, callbacks, commands."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.models import Job, TailoredResult, SearchConfig


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_job(job_id: str = "job-1") -> Job:
    return Job(
        job_id=job_id,
        title="ML Engineer",
        company="DeepMind",
        location="London, UK",
        url=f"https://linkedin.com/jobs/view/{job_id}/",
        description="Build ML systems.",
    )


def _make_result(job: Job, keywords: list[str] | None = None) -> TailoredResult:
    return TailoredResult(
        job=job,
        preview_data={"job_id": "rm-1", "resume_preview": {}, "improvements": []},
        rm_job_id="rm-1",
        master_resume_id="master-1",
        keywords_added=keywords or ["PyTorch", "RLHF"],
    )


def _mock_app():
    app = MagicMock()
    app.bot = AsyncMock()
    app.bot.send_message = AsyncMock()
    return app


def _mock_update():
    upd = MagicMock()
    upd.message = AsyncMock()
    upd.message.reply_text = AsyncMock()
    return upd


# ── notify_job ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notify_job_sends_message_with_company_and_title():
    from agent.notifier import notify_job

    app = _mock_app()
    result = _make_result(_make_job())

    await notify_job(app, "12345", result)

    app.bot.send_message.assert_awaited_once()
    kwargs = app.bot.send_message.call_args.kwargs
    assert kwargs["chat_id"] == "12345"
    assert "DeepMind" in kwargs["text"]
    assert "ML Engineer" in kwargs["text"]


@pytest.mark.asyncio
async def test_notify_job_uses_markdownv2():
    from agent.notifier import notify_job

    app = _mock_app()
    await notify_job(app, "12345", _make_result(_make_job()))

    kwargs = app.bot.send_message.call_args.kwargs
    assert kwargs["parse_mode"] == "MarkdownV2"


@pytest.mark.asyncio
async def test_notify_job_includes_inline_keyboard():
    from agent.notifier import notify_job
    from telegram import InlineKeyboardMarkup

    app = _mock_app()
    await notify_job(app, "12345", _make_result(_make_job("abc")))

    kwargs = app.bot.send_message.call_args.kwargs
    markup = kwargs["reply_markup"]
    assert isinstance(markup, InlineKeyboardMarkup)
    # confirm + skip buttons
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    callback_data = {b.callback_data for b in buttons}
    assert "confirm:abc" in callback_data
    assert "skip:abc" in callback_data


@pytest.mark.asyncio
async def test_notify_job_shows_keyword_count():
    from agent.notifier import notify_job

    app = _mock_app()
    job = _make_job()
    result = _make_result(job, keywords=["PyTorch", "JAX", "RLHF"])
    await notify_job(app, "12345", result)

    text = app.bot.send_message.call_args.kwargs["text"]
    assert "3" in text  # keyword count


@pytest.mark.asyncio
async def test_notify_job_no_keywords_shows_dash():
    from agent.notifier import notify_job

    app = _mock_app()
    result = _make_result(_make_job(), keywords=[])
    await notify_job(app, "12345", result)

    text = app.bot.send_message.call_args.kwargs["text"]
    assert "—" in text


# ── notify_error ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notify_error_sends_warning_prefix():
    from agent.notifier import notify_error

    app = _mock_app()
    await notify_error(app, "111", "Something went wrong")

    app.bot.send_message.assert_awaited_once()
    text = app.bot.send_message.call_args[1]["text"]
    assert "Something went wrong" in text
    assert "⚠️" in text


# ── _handle_confirm ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_confirm_no_preview_data_sends_warning():
    """If preview_data is missing, send a warning and do not call confirm_resume."""
    from agent.notifier import _handle_confirm
    from agent.config import Settings

    settings = MagicMock(spec=Settings)
    query = MagicMock()
    query.message = AsyncMock()
    query.message.reply_text = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()

    with patch("agent.notifier.db.get_preview_data", return_value=None):
        await _handle_confirm(query, settings, "job-1")

    query.message.reply_text.assert_awaited_once()
    text = query.message.reply_text.call_args.args[0]
    assert "⚠️" in text


@pytest.mark.asyncio
async def test_handle_confirm_no_meta_sends_warning():
    from agent.notifier import _handle_confirm
    from agent.config import Settings

    settings = MagicMock(spec=Settings)
    query = MagicMock()
    query.message = AsyncMock()
    query.message.reply_text = AsyncMock()

    with (
        patch("agent.notifier.db.get_preview_data", return_value={"job_id": "rm-1"}),
        patch("agent.notifier.db.get_job_meta", return_value=None),
    ):
        await _handle_confirm(query, settings, "job-1")

    query.message.reply_text.assert_awaited_once()
    text = query.message.reply_text.call_args.args[0]
    assert "⚠️" in text


@pytest.mark.asyncio
async def test_handle_confirm_success_confirms_and_shows_pdf_url():
    from agent.notifier import _handle_confirm
    from agent.config import Settings

    settings = MagicMock(spec=Settings)
    settings.resume_matcher_url = "http://rm:8000"
    query = MagicMock()
    query.message = AsyncMock()
    query.message.reply_text = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()

    preview = {"job_id": "rm-1", "resume_preview": {}, "improvements": []}

    with (
        patch("agent.notifier.db.get_preview_data", return_value=preview),
        patch("agent.notifier.db.get_job_meta", return_value={"master_resume_id": "master-1"}),
        patch("agent.notifier.improver.confirm_resume", new=AsyncMock(return_value="confirmed-xyz")),
        patch("agent.notifier.db.confirm_job"),
    ):
        await _handle_confirm(query, settings, "job-1")

    reply_text = query.message.reply_text.call_args.args[0]
    assert "confirmed-xyz" in reply_text
    assert "http://rm:8000" in reply_text


@pytest.mark.asyncio
async def test_handle_confirm_failed_confirm_resume_sends_warning():
    from agent.notifier import _handle_confirm

    settings = MagicMock()
    settings.resume_matcher_url = "http://rm:8000"
    query = MagicMock()
    query.message = AsyncMock()
    query.message.reply_text = AsyncMock()

    preview = {"job_id": "rm-1", "resume_preview": {}, "improvements": []}

    with (
        patch("agent.notifier.db.get_preview_data", return_value=preview),
        patch("agent.notifier.db.get_job_meta", return_value={"master_resume_id": "master-1"}),
        patch("agent.notifier.improver.confirm_resume", new=AsyncMock(return_value=None)),
    ):
        await _handle_confirm(query, settings, "job-1")

    text = query.message.reply_text.call_args.args[0]
    assert "⚠️" in text


# ── _handle_skip ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_skip_marks_job_skipped():
    from agent.notifier import _handle_skip
    from agent.config import Settings

    settings = MagicMock(spec=Settings)
    query = MagicMock()
    query.message = MagicMock()
    query.message.text = "🏢 *DeepMind* — ML Engineer\nsome text"
    query.edit_message_text = AsyncMock()

    with patch("agent.notifier.db.skip_job") as mock_skip:
        await _handle_skip(query, settings, "job-1")

    mock_skip.assert_called_once()
    assert mock_skip.call_args[0][0] == "job-1"


# ── cmd_status ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_status_shows_counts():
    from agent.notifier import cmd_status

    update = _mock_update()
    context = MagicMock()

    with patch("agent.notifier.db.get_stats", return_value={
        "notified": 3, "confirmed": 2, "skipped": 1
    }):
        await cmd_status(update, context)

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args.args[0]
    assert "3" in text
    assert "2" in text
    assert "1" in text


# ── cmd_list ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_list_shows_confirmed_jobs():
    from agent.notifier import cmd_list

    update = _mock_update()
    context = MagicMock()
    context.bot_data = {"settings": MagicMock(resume_matcher_url="http://rm:8000")}

    mock_jobs = [
        {"job_id": "j1", "title": "ML Engineer", "company": "DeepMind",
         "confirmed_resume_id": "res-1"},
    ]
    with patch("agent.notifier.db.get_recent_confirmed", return_value=mock_jobs):
        await cmd_list(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "ML Engineer" in text
    assert "DeepMind" in text


@pytest.mark.asyncio
async def test_cmd_list_empty():
    from agent.notifier import cmd_list

    update = _mock_update()
    context = MagicMock()
    context.bot_data = {"settings": MagicMock(resume_matcher_url="http://rm:8000")}

    with patch("agent.notifier.db.get_recent_confirmed", return_value=[]):
        await cmd_list(update, context)

    update.message.reply_text.assert_awaited_once()


# ── cmd_config ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_config_shows_current_settings():
    from agent.notifier import cmd_config
    from agent.models import SearchConfig

    update = _mock_update()
    context = MagicMock()
    sc = SearchConfig(
        keywords=["AI Engineer"],
        location="Germany",
        experience_level=["MID_SENIOR_LEVEL"],
        blacklist_companies=[],
        max_jobs_per_run=20,
    )
    with patch("agent.notifier.cfg.get_search_config", return_value=sc):
        await cmd_config(update, context)

    update.message.reply_text.assert_awaited_once()
    call_kwargs = update.message.reply_text.call_args.kwargs
    assert call_kwargs.get("parse_mode") == "MarkdownV2"


# ── cmd_set_keywords / cmd_set_location / cmd_set_max ─────────────────────────


@pytest.mark.asyncio
async def test_cmd_set_keywords_updates_and_confirms():
    from agent.notifier import cmd_set_keywords

    update = _mock_update()
    context = MagicMock()
    context.args = ["AI", "Engineer,", "ML", "Engineer"]

    with patch("agent.notifier.cfg.set_keywords") as mock_set:
        await cmd_set_keywords(update, context)

    mock_set.assert_called_once()
    update.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_set_keywords_no_args_shows_usage():
    from agent.notifier import cmd_set_keywords

    update = _mock_update()
    context = MagicMock()
    context.args = []

    with patch("agent.notifier.cfg.set_keywords") as mock_set:
        await cmd_set_keywords(update, context)

    mock_set.assert_not_called()
    update.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_set_location_updates():
    from agent.notifier import cmd_set_location

    update = _mock_update()
    context = MagicMock()
    context.args = ["Berlin,", "Germany"]

    with patch("agent.notifier.cfg.set_location") as mock_set:
        await cmd_set_location(update, context)

    mock_set.assert_called_once_with("Berlin, Germany")


@pytest.mark.asyncio
async def test_cmd_set_max_updates():
    from agent.notifier import cmd_set_max

    update = _mock_update()
    context = MagicMock()
    context.args = ["15"]

    with patch("agent.notifier.cfg.set_max_jobs") as mock_set:
        await cmd_set_max(update, context)

    mock_set.assert_called_once_with(15)


@pytest.mark.asyncio
async def test_cmd_set_max_non_digit_shows_usage():
    from agent.notifier import cmd_set_max

    update = _mock_update()
    context = MagicMock()
    context.args = ["abc"]

    with patch("agent.notifier.cfg.set_max_jobs") as mock_set:
        await cmd_set_max(update, context)

    mock_set.assert_not_called()
    update.message.reply_text.assert_awaited_once()
