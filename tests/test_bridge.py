import json
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import asdict

import pytest

from core.bridge import ClaudeResponse, send_message


@pytest.fixture
def mock_claude_success():
    """Simulates successful claude -p JSON output."""
    return json.dumps({
        "type": "result",
        "result": "Hello! How can I help?",
        "session_id": "sess-abc-123",
        "cost_usd": 0.003,
        "usage": {"input_tokens": 50, "output_tokens": 20},
    })


@pytest.fixture
def mock_claude_error():
    return json.dumps({
        "type": "error",
        "error": "Something went wrong",
    })


@pytest.mark.asyncio
async def test_send_message_new_session(mock_claude_success):
    proc = AsyncMock()
    proc.communicate.return_value = (mock_claude_success.encode(), b"")
    proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
        resp = await send_message("Hello", project_dir="/tmp/bot")

    assert resp.text == "Hello! How can I help?"
    assert resp.session_id == "sess-abc-123"
    assert resp.cost_usd == 0.003

    cmd_args = mock_exec.call_args[0]
    assert "--resume" not in cmd_args
    assert "--output-format" in cmd_args
    assert "json" in cmd_args


@pytest.mark.asyncio
async def test_send_message_resume_session(mock_claude_success):
    proc = AsyncMock()
    proc.communicate.return_value = (mock_claude_success.encode(), b"")
    proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
        resp = await send_message("Hi again", session_id="sess-abc-123", project_dir="/tmp/bot")

    cmd_args = mock_exec.call_args[0]
    assert "--resume" in cmd_args
    assert "sess-abc-123" in cmd_args


@pytest.mark.asyncio
async def test_send_message_strips_claudecode_env():
    proc = AsyncMock()
    proc.communicate.return_value = (
        json.dumps({"type": "result", "result": "ok", "session_id": "s1", "cost_usd": 0, "usage": {}}).encode(),
        b"",
    )
    proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
        with patch.dict("os.environ", {"CLAUDECODE": "1", "HOME": "/tmp"}):
            await send_message("test", project_dir="/tmp/bot")

    env = mock_exec.call_args[1].get("env", {})
    assert "CLAUDECODE" not in env


@pytest.mark.asyncio
async def test_send_message_error_response(mock_claude_error):
    proc = AsyncMock()
    proc.communicate.return_value = (mock_claude_error.encode(), b"")
    proc.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        resp = await send_message("Hello", project_dir="/tmp/bot")

    assert resp.text == "Something went wrong"
    assert resp.is_error is True
