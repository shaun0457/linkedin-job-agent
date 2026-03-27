"""Tests for agent/notifier.py helper functions."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import agent.db as db_module
from agent.notifier import notify_run_summary, cmd_search_config, _esc


# ── notify_run_summary ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notify_run_summary_sends_message():
    app = MagicMock()
    app.bot.send_message = AsyncMock()

    await notify_run_summary(app, "chat-1", found=5, tailored=4, failed=1)

    app.bot.send_message.assert_awaited_once()
    call_kwargs = app.bot.send_message.call_args
    assert call_kwargs.kwargs["chat_id"] == "chat-1"
    assert call_kwargs.kwargs["parse_mode"] == "MarkdownV2"
    text = call_kwargs.kwargs["text"]
    assert "5" in text
    assert "4" in text
    assert "1" in text


@pytest.mark.asyncio
async def test_notify_run_summary_skips_when_found_zero():
    app = MagicMock()
    app.bot.send_message = AsyncMock()

    await notify_run_summary(app, "chat-1", found=0, tailored=0, failed=0)

    app.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_run_summary_all_failed():
    app = MagicMock()
    app.bot.send_message = AsyncMock()

    await notify_run_summary(app, "chat-2", found=3, tailored=0, failed=3)

    app.bot.send_message.assert_awaited_once()
    text = app.bot.send_message.call_args.kwargs["text"]
    assert "3" in text
    assert "0" in text


# ── cmd_search_config ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_jobs.db"
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    db_module.init_db()


@pytest.mark.asyncio
async def test_cmd_search_config_sends_full_config(tmp_path, monkeypatch):
    from agent import config as cfg
    from agent.models import SearchConfig

    mock_config = SearchConfig(
        keywords=["AI Engineer"],
        location="Germany",
        experience_level=["MID_SENIOR_LEVEL"],
        blacklist_companies=["SpamCorp"],
        max_jobs_per_run=10,
    )
    with patch("agent.notifier.cfg.get_search_config", return_value=mock_config):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await cmd_search_config(update, context)

    update.message.reply_text.assert_awaited_once()
    call_kwargs = update.message.reply_text.call_args
    assert call_kwargs.kwargs.get("parse_mode") == "MarkdownV2"
    text = call_kwargs.args[0]
    # Underscores are escaped in MarkdownV2
    assert "MID\\_SENIOR\\_LEVEL" in text
    assert "SpamCorp" in text
    assert "Germany" in text
    assert "AI Engineer" in text


@pytest.mark.asyncio
async def test_cmd_search_config_empty_blacklist(tmp_path, monkeypatch):
    from agent.models import SearchConfig

    mock_config = SearchConfig(
        keywords=["ML Engineer"],
        location="UK",
        experience_level=["SENIOR_LEVEL"],
        blacklist_companies=[],
        max_jobs_per_run=5,
    )
    with patch("agent.notifier.cfg.get_search_config", return_value=mock_config):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await cmd_search_config(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "—" in text
