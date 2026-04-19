"""Tests for cmd_run and cmd_help."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_update():
    upd = MagicMock()
    upd.message = AsyncMock()
    upd.message.reply_text = AsyncMock()
    return upd


# ── cmd_run ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_run_with_pipeline_creates_task():
    """When run_pipeline is registered, cmd_run triggers it via asyncio.create_task."""
    from agent.notifier import cmd_run
    import asyncio

    update = _mock_update()
    context = MagicMock()

    pipeline_called = []

    async def fake_pipeline():
        pipeline_called.append(True)

    context.bot_data = {"run_pipeline": fake_pipeline}

    with patch("agent.notifier.asyncio.create_task") as mock_task:
        await cmd_run(update, context)

    mock_task.assert_called_once()
    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args.args[0]
    assert "▶️" in text or "觸發" in text


@pytest.mark.asyncio
async def test_cmd_run_without_pipeline_sends_warning():
    """When run_pipeline is not in bot_data, cmd_run sends a warning."""
    from agent.notifier import cmd_run

    update = _mock_update()
    context = MagicMock()
    context.bot_data = {}  # no run_pipeline key

    await cmd_run(update, context)

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args.args[0]
    assert "⚠️" in text


@pytest.mark.asyncio
async def test_cmd_run_pipeline_none_sends_warning():
    """When run_pipeline is explicitly None, cmd_run sends a warning."""
    from agent.notifier import cmd_run

    update = _mock_update()
    context = MagicMock()
    context.bot_data = {"run_pipeline": None}

    await cmd_run(update, context)

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args.args[0]
    assert "⚠️" in text


# ── cmd_help ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_help_sends_markdownv2():
    from agent.notifier import cmd_help

    update = _mock_update()
    context = MagicMock()

    await cmd_help(update, context)

    update.message.reply_text.assert_awaited_once()
    kwargs = update.message.reply_text.call_args.kwargs
    assert kwargs.get("parse_mode") == "MarkdownV2"


@pytest.mark.asyncio
async def test_cmd_help_lists_all_key_commands():
    from agent.notifier import cmd_help

    update = _mock_update()
    context = MagicMock()

    await cmd_help(update, context)

    text = update.message.reply_text.call_args.args[0]
    # All major commands should be mentioned (underscores are MarkdownV2-escaped as \_)
    for cmd in ["/run", "/status", "/pending", "/list", "/retry", "/help"]:
        assert cmd in text, f"Missing {cmd} in /help output"
    assert "search" in text and "config" in text, "Missing /search_config in /help output"
