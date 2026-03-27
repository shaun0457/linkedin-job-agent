"""TDD tests for experience level validation in cmd_set_experience_level."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_update():
    upd = MagicMock()
    upd.message = AsyncMock()
    upd.message.reply_text = AsyncMock()
    return upd


# ── models.VALID_EXPERIENCE_LEVELS ────────────────────────────────────────────


def test_valid_experience_levels_constant_exists():
    from agent.models import VALID_EXPERIENCE_LEVELS
    assert isinstance(VALID_EXPERIENCE_LEVELS, (set, frozenset, list, tuple))


def test_valid_experience_levels_contains_linkedin_values():
    from agent.models import VALID_EXPERIENCE_LEVELS
    expected = {"INTERNSHIP", "ENTRY_LEVEL", "ASSOCIATE", "MID_SENIOR_LEVEL", "DIRECTOR", "EXECUTIVE"}
    for level in expected:
        assert level in VALID_EXPERIENCE_LEVELS, f"Missing {level}"


# ── cmd_set_experience_level validation ───────────────────────────────────────


@pytest.mark.asyncio
async def test_set_experience_level_valid_levels_no_warning():
    """Valid LinkedIn levels → updates config without warning."""
    from agent.notifier import cmd_set_experience_level

    update = _mock_update()
    context = MagicMock()
    context.args = ["MID_SENIOR_LEVEL,", "ENTRY_LEVEL"]

    with patch("agent.notifier.cfg.set_experience_level") as mock_set:
        await cmd_set_experience_level(update, context)

    mock_set.assert_called_once()
    text = update.message.reply_text.call_args.args[0]
    assert "⚠️" not in text
    assert "✅" in text


@pytest.mark.asyncio
async def test_set_experience_level_unknown_level_warns():
    """Unknown level → saves but includes warning in reply."""
    from agent.notifier import cmd_set_experience_level

    update = _mock_update()
    context = MagicMock()
    context.args = ["SOME_INVALID_LEVEL"]

    with patch("agent.notifier.cfg.set_experience_level") as mock_set:
        await cmd_set_experience_level(update, context)

    # Still saves — just warns
    mock_set.assert_called_once()
    text = update.message.reply_text.call_args.args[0]
    assert "⚠️" in text or "無效" in text or "invalid" in text.lower()


@pytest.mark.asyncio
async def test_set_experience_level_mixed_valid_invalid_warns():
    """Mix of valid and invalid levels → warns but saves all."""
    from agent.notifier import cmd_set_experience_level

    update = _mock_update()
    context = MagicMock()
    context.args = ["MID_SENIOR_LEVEL,", "MADE_UP_LEVEL"]

    with patch("agent.notifier.cfg.set_experience_level") as mock_set:
        await cmd_set_experience_level(update, context)

    mock_set.assert_called_once()
    levels = mock_set.call_args[0][0]
    assert "MID_SENIOR_LEVEL" in levels
    assert "MADE_UP_LEVEL" in levels


@pytest.mark.asyncio
async def test_set_experience_level_empty_after_split():
    """Input of only commas/spaces yields warning, no config update."""
    from agent.notifier import cmd_set_experience_level

    update = _mock_update()
    context = MagicMock()
    context.args = [" ", ",", " ", ",", " "]

    with patch("agent.notifier.cfg.set_experience_level") as mock_set:
        await cmd_set_experience_level(update, context)

    mock_set.assert_not_called()
    text = update.message.reply_text.call_args.args[0]
    assert "至少一個" in text
