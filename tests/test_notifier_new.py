"""Tests for new notifier functions: notify_run_summary, cmd_search_config (TDD)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


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


@pytest.mark.asyncio
async def test_notify_run_summary_english_format():
    """notify_run_summary uses English one-liner: 'Run complete: X new jobs found, ...'"""
    from agent.notifier import notify_run_summary

    mock_app = MagicMock()
    mock_app.bot = AsyncMock()
    mock_app.bot.send_message = AsyncMock()

    await notify_run_summary(mock_app, "12345", found=7, tailored=5, failed=2)

    call_kwargs = mock_app.bot.send_message.call_args
    kwargs = call_kwargs.kwargs if call_kwargs.kwargs else call_kwargs[1]
    text = kwargs.get("text", "")
    assert "Run complete" in text
    assert "7" in text
    assert "5" in text
    assert "2" in text


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
