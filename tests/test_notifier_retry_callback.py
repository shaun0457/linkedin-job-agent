"""Tests for cmd_retry and handle_callback routing."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_update():
    upd = MagicMock()
    upd.message = AsyncMock()
    upd.message.reply_text = AsyncMock()
    return upd


# ── cmd_retry ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_retry_no_args_shows_usage():
    from agent.notifier import cmd_retry

    update = _mock_update()
    context = MagicMock()
    context.args = []

    await cmd_retry(update, context)

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args.args[0]
    assert "retry" in text.lower() or "/retry" in text


@pytest.mark.asyncio
async def test_cmd_retry_unknown_job_id_shows_error():
    from agent.notifier import cmd_retry

    update = _mock_update()
    context = MagicMock()
    context.args = ["nonexistent-job"]
    context.bot_data = {"settings": MagicMock(resume_matcher_url="http://rm:8000")}

    with patch("agent.notifier.db.get_preview_data", return_value=None):
        await cmd_retry(update, context)

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args.args[0]
    assert "nonexistent-job" in text or "找不到" in text


@pytest.mark.asyncio
async def test_cmd_retry_no_meta_shows_warning():
    from agent.notifier import cmd_retry

    update = _mock_update()
    context = MagicMock()
    context.args = ["job-1"]
    context.bot_data = {"settings": MagicMock(resume_matcher_url="http://rm:8000")}

    preview = {"job_id": "rm-1", "resume_preview": {}, "improvements": []}
    with (
        patch("agent.notifier.db.get_preview_data", return_value=preview),
        patch("agent.notifier.db.get_job_meta", return_value=None),
    ):
        await cmd_retry(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "⚠️" in text


@pytest.mark.asyncio
async def test_cmd_retry_confirm_failure_shows_warning():
    from agent.notifier import cmd_retry

    update = _mock_update()
    context = MagicMock()
    context.args = ["job-1"]
    context.bot_data = {"settings": MagicMock(resume_matcher_url="http://rm:8000")}

    preview = {"job_id": "rm-1", "resume_preview": {}, "improvements": []}
    with (
        patch("agent.notifier.db.get_preview_data", return_value=preview),
        patch("agent.notifier.db.get_job_meta", return_value={"master_resume_id": "master-1"}),
        patch("agent.notifier.improver.confirm_resume", new=AsyncMock(return_value=None)),
    ):
        await cmd_retry(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "⚠️" in text


@pytest.mark.asyncio
async def test_cmd_retry_success_shows_pdf_url():
    from agent.notifier import cmd_retry

    update = _mock_update()
    context = MagicMock()
    context.args = ["job-1"]
    context.bot_data = {"settings": MagicMock(resume_matcher_url="http://rm:8000")}

    preview = {"job_id": "rm-1", "resume_preview": {}, "improvements": []}
    with (
        patch("agent.notifier.db.get_preview_data", return_value=preview),
        patch("agent.notifier.db.get_job_meta", return_value={"master_resume_id": "master-1"}),
        patch("agent.notifier.improver.confirm_resume", new=AsyncMock(return_value="confirmed-abc")),
        patch("agent.notifier.db.confirm_job") as mock_confirm,
    ):
        await cmd_retry(update, context)

    mock_confirm.assert_called_once_with("job-1", "confirmed-abc", mock_confirm.call_args[0][2])
    text = update.message.reply_text.call_args.args[0]
    assert "confirmed-abc" in text
    assert "http://rm:8000" in text


# ── handle_callback ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_callback_routes_confirm():
    """callback_data 'confirm:job-1' → _handle_confirm called with 'job-1'."""
    from agent.notifier import handle_callback

    query = MagicMock()
    query.answer = AsyncMock()
    query.data = "confirm:job-abc"
    query.message = AsyncMock()
    query.message.reply_text = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()

    update = MagicMock()
    update.callback_query = query
    context = MagicMock()
    context.bot_data = {"settings": MagicMock(resume_matcher_url="http://rm:8000")}

    with patch("agent.notifier._handle_confirm", new=AsyncMock()) as mock_confirm:
        await handle_callback(update, context)

    mock_confirm.assert_awaited_once()
    assert mock_confirm.call_args[0][2] == "job-abc"


@pytest.mark.asyncio
async def test_handle_callback_routes_skip():
    """callback_data 'skip:job-1' → _handle_skip called with 'job-1'."""
    from agent.notifier import handle_callback

    query = MagicMock()
    query.answer = AsyncMock()
    query.data = "skip:job-xyz"
    query.message = MagicMock()
    query.message.text = "line 1"

    update = MagicMock()
    update.callback_query = query
    context = MagicMock()
    context.bot_data = {"settings": MagicMock()}

    with patch("agent.notifier._handle_skip", new=AsyncMock()) as mock_skip:
        await handle_callback(update, context)

    mock_skip.assert_awaited_once()
    assert mock_skip.call_args[0][2] == "job-xyz"


@pytest.mark.asyncio
async def test_handle_callback_unknown_data_is_noop():
    """Unknown callback data does not call confirm or skip."""
    from agent.notifier import handle_callback

    query = MagicMock()
    query.answer = AsyncMock()
    query.data = "unknown:something"

    update = MagicMock()
    update.callback_query = query
    context = MagicMock()
    context.bot_data = {"settings": MagicMock()}

    with (
        patch("agent.notifier._handle_confirm", new=AsyncMock()) as mock_confirm,
        patch("agent.notifier._handle_skip", new=AsyncMock()) as mock_skip,
    ):
        await handle_callback(update, context)

    mock_confirm.assert_not_awaited()
    mock_skip.assert_not_awaited()
