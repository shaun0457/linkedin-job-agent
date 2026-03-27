"""TDD tests for weekly stats in cmd_status."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_update():
    upd = MagicMock()
    upd.message = AsyncMock()
    upd.message.reply_text = AsyncMock()
    return upd


@pytest.mark.asyncio
async def test_cmd_status_shows_weekly_stats():
    """cmd_status must include weekly counts alongside daily counts."""
    from agent.notifier import cmd_status

    update = _mock_update()
    context = MagicMock()

    daily = {"notified": 1, "confirmed": 1, "skipped": 0}
    weekly = {"notified": 3, "confirmed": 5, "skipped": 2}

    def fake_get_stats(since: str):
        # daily starts with current date, weekly is 7 days back
        if since.startswith("2") and len(since) == 19:
            # determine by prefix pattern — weekly cutoff is earlier
            return weekly if "T00:00:00" not in since or since < "2026" else daily
        return daily

    with patch("agent.notifier.db.get_stats") as mock_stats:
        mock_stats.side_effect = [daily, weekly]  # first call = today, second = week
        await cmd_status(update, context)

    # Should call get_stats twice — today + 7 days ago
    assert mock_stats.call_count == 2
    text = update.message.reply_text.call_args.args[0]
    # Both today and week numbers should appear
    assert "1" in text   # daily confirmed
    assert "5" in text   # weekly confirmed


@pytest.mark.asyncio
async def test_cmd_status_weekly_since_7_days_ago():
    """Second get_stats call must use a date ~7 days in the past."""
    from agent.notifier import cmd_status
    from datetime import datetime, timezone, timedelta

    update = _mock_update()
    context = MagicMock()

    with patch("agent.notifier.db.get_stats", return_value={}) as mock_stats:
        await cmd_status(update, context)

    assert mock_stats.call_count == 2
    weekly_since = mock_stats.call_args_list[1][1].get("since") or mock_stats.call_args_list[1][0][0]
    # Should be roughly 7 days ago (within tolerance of 1 day)
    parsed = datetime.fromisoformat(weekly_since.replace("Z", "+00:00"))
    days_ago = (datetime.now(timezone.utc) - parsed).days
    assert 6 <= days_ago <= 8, f"Expected ~7 days ago, got {days_ago}"


@pytest.mark.asyncio
async def test_cmd_status_shows_today_label():
    from agent.notifier import cmd_status

    update = _mock_update()
    context = MagicMock()

    with patch("agent.notifier.db.get_stats", return_value={"notified": 0}):
        await cmd_status(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "今日" in text or "今天" in text


@pytest.mark.asyncio
async def test_cmd_status_shows_weekly_label():
    from agent.notifier import cmd_status

    update = _mock_update()
    context = MagicMock()

    with patch("agent.notifier.db.get_stats", return_value={}):
        await cmd_status(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "本週" in text or "7天" in text or "週" in text
