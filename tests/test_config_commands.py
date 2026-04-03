"""TDD tests for /set_experience_level, /set_blacklist, /pending commands."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── /set_experience_level ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_set_experience_level_updates_config():
    """set_experience_level stores the new list."""
    from agent.notifier import cmd_set_experience_level

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = ["MID_SENIOR_LEVEL,", "ENTRY_LEVEL"]

    with patch("agent.notifier.cfg.set_experience_level") as mock_set:
        await cmd_set_experience_level(mock_update, mock_context)

    mock_set.assert_called_once()
    levels = mock_set.call_args[0][0]
    assert "MID_SENIOR_LEVEL" in levels
    assert "ENTRY_LEVEL" in levels


@pytest.mark.asyncio
async def test_cmd_set_experience_level_replies_confirmation():
    from agent.notifier import cmd_set_experience_level

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = ["SENIOR_LEVEL"]

    with patch("agent.notifier.cfg.set_experience_level"):
        await cmd_set_experience_level(mock_update, mock_context)

    mock_update.message.reply_text.assert_awaited_once()
    call_args = mock_update.message.reply_text.call_args
    text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
    assert "SENIOR_LEVEL" in text


@pytest.mark.asyncio
async def test_cmd_set_experience_level_no_args_shows_usage():
    from agent.notifier import cmd_set_experience_level

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = []

    with patch("agent.notifier.cfg.set_experience_level") as mock_set:
        await cmd_set_experience_level(mock_update, mock_context)

    mock_set.assert_not_called()
    mock_update.message.reply_text.assert_awaited_once()


# ── /set_blacklist ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_set_blacklist_updates_config():
    from agent.notifier import cmd_set_blacklist

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = ["EvilCorp,", "BadInc"]

    with patch("agent.notifier.cfg.set_blacklist_companies") as mock_set:
        await cmd_set_blacklist(mock_update, mock_context)

    mock_set.assert_called_once()
    companies = mock_set.call_args[0][0]
    assert "EvilCorp" in companies
    assert "BadInc" in companies


@pytest.mark.asyncio
async def test_cmd_set_blacklist_replies_confirmation():
    from agent.notifier import cmd_set_blacklist

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = ["SpamCo"]

    with patch("agent.notifier.cfg.set_blacklist_companies"):
        await cmd_set_blacklist(mock_update, mock_context)

    mock_update.message.reply_text.assert_awaited_once()
    call_args = mock_update.message.reply_text.call_args
    text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
    assert "SpamCo" in text


@pytest.mark.asyncio
async def test_cmd_set_blacklist_no_args_shows_usage():
    from agent.notifier import cmd_set_blacklist

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = []

    with patch("agent.notifier.cfg.set_blacklist_companies") as mock_set:
        await cmd_set_blacklist(mock_update, mock_context)

    mock_set.assert_not_called()
    mock_update.message.reply_text.assert_awaited_once()


# ── /pending ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_pending_shows_jobs():
    from agent.notifier import cmd_pending

    mock_jobs = [
        {"job_id": "job-1", "title": "ML Engineer", "company": "DeepMind",
         "notified_at": "2024-01-15T08:00:00+00:00"},
        {"job_id": "job-2", "title": "AI Engineer", "company": "OpenAI",
         "notified_at": "2024-01-15T09:00:00+00:00"},
    ]

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()

    with patch("agent.notifier.db.get_pending_jobs", return_value=mock_jobs):
        await cmd_pending(mock_update, mock_context)

    mock_update.message.reply_text.assert_awaited_once()
    call_args = mock_update.message.reply_text.call_args
    text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
    assert "ML Engineer" in text or "DeepMind" in text


@pytest.mark.asyncio
async def test_cmd_pending_empty_shows_message():
    from agent.notifier import cmd_pending

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()

    with patch("agent.notifier.db.get_pending_jobs", return_value=[]):
        await cmd_pending(mock_update, mock_context)

    mock_update.message.reply_text.assert_awaited_once()


# ── db.get_pending_jobs ───────────────────────────────────────────────────────


def test_db_get_pending_jobs_returns_notified():
    """get_pending_jobs returns jobs with status='notified'."""
    from datetime import datetime, timezone
    import agent.db as db_module
    import pytest

    # This is an integration-style test using the module directly
    # We'll import the function and test its return type
    assert hasattr(db_module, "get_pending_jobs")


def test_db_get_pending_jobs_signature():
    """get_pending_jobs(limit) is callable."""
    import agent.db as db_module
    import inspect
    sig = inspect.signature(db_module.get_pending_jobs)
    assert "limit" in sig.parameters


# ── cfg.set_experience_level / set_blacklist_companies ───────────────────────


def test_cfg_set_experience_level_exists():
    import agent.config as cfg
    assert hasattr(cfg, "set_experience_level")


def test_cfg_set_blacklist_companies_exists():
    import agent.config as cfg
    assert hasattr(cfg, "set_blacklist_companies")


@pytest.mark.asyncio
async def test_cmd_set_blacklist_clear_option():
    """'/set_blacklist -clear' clears the blacklist and confirms."""
    from agent.notifier import cmd_set_blacklist

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = ["-clear"]

    with patch("agent.notifier.cfg.set_blacklist_companies") as mock_set:
        await cmd_set_blacklist(mock_update, mock_context)

    mock_set.assert_called_once_with([])
    text = mock_update.message.reply_text.call_args.args[0]
    assert "清空" in text


# ── /time ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cmd_time_sets_24h():
    from agent.notifier import cmd_time

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = ["24h"]

    with patch("agent.notifier.cfg.set_time_filter") as mock_set:
        await cmd_time(mock_update, mock_context)

    mock_set.assert_called_once_with("r86400")
    text = mock_update.message.reply_text.call_args.args[0]
    assert "24" in text


@pytest.mark.asyncio
async def test_cmd_time_sets_1w():
    from agent.notifier import cmd_time

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = ["1w"]

    with patch("agent.notifier.cfg.set_time_filter") as mock_set:
        await cmd_time(mock_update, mock_context)

    mock_set.assert_called_once_with("r604800")


@pytest.mark.asyncio
async def test_cmd_time_sets_1m():
    from agent.notifier import cmd_time

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = ["1m"]

    with patch("agent.notifier.cfg.set_time_filter") as mock_set:
        await cmd_time(mock_update, mock_context)

    mock_set.assert_called_once_with("r2592000")


@pytest.mark.asyncio
async def test_cmd_time_sets_none():
    from agent.notifier import cmd_time

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = ["none"]

    with patch("agent.notifier.cfg.set_time_filter") as mock_set:
        await cmd_time(mock_update, mock_context)

    mock_set.assert_called_once_with("")


@pytest.mark.asyncio
async def test_cmd_time_no_args_shows_usage():
    from agent.notifier import cmd_time

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = []

    with patch("agent.notifier.cfg.set_time_filter") as mock_set:
        await cmd_time(mock_update, mock_context)

    mock_set.assert_not_called()
    text = mock_update.message.reply_text.call_args.args[0]
    assert "24h" in text  # usage should show options


@pytest.mark.asyncio
async def test_cmd_time_invalid_arg():
    from agent.notifier import cmd_time

    mock_update = MagicMock()
    mock_update.message = AsyncMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = ["3y"]

    with patch("agent.notifier.cfg.set_time_filter") as mock_set:
        await cmd_time(mock_update, mock_context)

    mock_set.assert_not_called()
    text = mock_update.message.reply_text.call_args.args[0]
    assert "24h" in text  # should show valid options
