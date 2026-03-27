"""Tests for /health command — Resume Matcher connectivity check."""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_update():
    upd = MagicMock()
    upd.message = AsyncMock()
    upd.message.reply_text = AsyncMock()
    return upd


def _mock_context(resume_matcher_url="http://localhost:8000"):
    ctx = MagicMock()
    settings = MagicMock()
    settings.resume_matcher_url = resume_matcher_url
    ctx.bot_data = {"settings": settings}
    return ctx


@pytest.mark.asyncio
async def test_cmd_health_reachable():
    """When Resume Matcher API responds successfully, reply with success message."""
    from agent.notifier import cmd_health

    update = _mock_update()
    context = _mock_context()

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("agent.notifier.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.get = AsyncMock(return_value=mock_response)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        await cmd_health(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "Resume Matcher" in text
    assert "\u2705" in text  # checkmark emoji


@pytest.mark.asyncio
async def test_cmd_health_unreachable():
    """When Resume Matcher API raises ConnectError, reply with unreachable message."""
    from agent.notifier import cmd_health

    update = _mock_update()
    context = _mock_context()

    with patch("agent.notifier.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        await cmd_health(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "Resume Matcher" in text
    assert "\u26a0\ufe0f" in text  # warning emoji


@pytest.mark.asyncio
async def test_cmd_health_timeout():
    """When Resume Matcher API raises TimeoutException, reply with timeout message."""
    from agent.notifier import cmd_health

    update = _mock_update()
    context = _mock_context()

    with patch("agent.notifier.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.get = AsyncMock(
            side_effect=httpx.TimeoutException("Request timed out")
        )
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        await cmd_health(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert "Resume Matcher" in text
    assert "\u23f1\ufe0f" in text  # stopwatch emoji
