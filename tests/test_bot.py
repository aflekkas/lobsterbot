from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from core.bot import handle_message, handle_new, is_authorized
from core.bridge import ClaudeResponse


@pytest.fixture
def mock_update():
    update = MagicMock()
    update.effective_user.id = 111
    update.effective_chat.id = 111
    update.message.text = "Hello bot"
    update.message.reply_text = AsyncMock()
    update.message.chat.send_action = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.bot.send_message = AsyncMock()
    return ctx


def test_is_authorized_allowed():
    assert is_authorized(111, [111, 222]) is True


def test_is_authorized_denied():
    assert is_authorized(999, [111, 222]) is False


@pytest.mark.asyncio
async def test_handle_message_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    with patch("core.bot._config", {"telegram": {"allowed_users": [111]}}):
        await handle_message(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    assert "not authorized" in mock_update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_handle_message_success(mock_update, mock_context):
    mock_response = ClaudeResponse(text="Hi there!", session_id="sess-1")

    with (
        patch("core.bot._config", {"telegram": {"allowed_users": [111]}}),
        patch("core.bot._sessions") as mock_sm,
        patch("core.bot.send_message", new_callable=AsyncMock, return_value=mock_response),
        patch("core.bot._project_dir", "/tmp/bot"),
    ):
        mock_sm.get_session.return_value = None
        await handle_message(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once_with("Hi there!")
    mock_sm.set_session.assert_called_once_with(111, "sess-1")


@pytest.mark.asyncio
async def test_handle_message_resumes_session(mock_update, mock_context):
    mock_response = ClaudeResponse(text="Continuing!", session_id="sess-1")

    with (
        patch("core.bot._config", {"telegram": {"allowed_users": [111]}}),
        patch("core.bot._sessions") as mock_sm,
        patch("core.bot.send_message", new_callable=AsyncMock, return_value=mock_response) as mock_send,
        patch("core.bot._project_dir", "/tmp/bot"),
    ):
        mock_sm.get_session.return_value = "sess-1"
        await handle_message(mock_update, mock_context)

    mock_send.assert_called_once_with("Hello bot", session_id="sess-1", project_dir="/tmp/bot")


@pytest.mark.asyncio
async def test_handle_new_clears_session(mock_update, mock_context):
    with (
        patch("core.bot._config", {"telegram": {"allowed_users": [111]}}),
        patch("core.bot._sessions") as mock_sm,
    ):
        await handle_new(mock_update, mock_context)

    mock_sm.clear_session.assert_called_once_with(111)
    mock_update.message.reply_text.assert_called_once()
