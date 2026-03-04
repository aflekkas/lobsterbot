import logging
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from core.bridge import send_message, ClaudeResponse
from core.config import load_config
from core.session import SessionManager

logger = logging.getLogger(__name__)

# Module-level state, initialized in main()
_config: dict = {}
_sessions: SessionManager | None = None
_project_dir: str = "."


def is_authorized(user_id: int, allowed: list[int]) -> bool:
    return user_id in allowed


async def handle_message(update: Update, context) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not is_authorized(user_id, _config["telegram"]["allowed_users"]):
        await update.message.reply_text("You are not authorized to use this bot.")
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    session_id = _sessions.get_session(chat_id)
    response = await send_message(
        update.message.text,
        session_id=session_id,
        project_dir=_project_dir,
    )

    if response.session_id:
        _sessions.set_session(chat_id, response.session_id)

    await update.message.reply_text(response.text)


async def handle_new(update: Update, context) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not is_authorized(user_id, _config["telegram"]["allowed_users"]):
        await update.message.reply_text("You are not authorized to use this bot.")
        return

    _sessions.clear_session(chat_id)
    await update.message.reply_text("Started a new conversation.")


async def handle_status(update: Update, context) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not is_authorized(user_id, _config["telegram"]["allowed_users"]):
        await update.message.reply_text("You are not authorized to use this bot.")
        return

    session_id = _sessions.get_session(chat_id)
    status = "Active session" if session_id else "No active session"
    await update.message.reply_text(f"Status: {status}\nSession: {session_id or 'none'}")


async def handle_help(update: Update, context) -> None:
    await update.message.reply_text(
        "/new — Start a new conversation\n"
        "/status — Session info\n"
        "/help — Show this message"
    )


def main():
    global _config, _sessions, _project_dir

    _project_dir = str(Path(__file__).resolve().parent.parent)
    _config = load_config()
    _sessions = SessionManager(Path(_project_dir) / "sessions.db")

    app = Application.builder().token(_config["telegram"]["token"]).build()
    app.add_handler(CommandHandler("new", handle_new))
    app.add_handler(CommandHandler("status", handle_status))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("start", handle_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
