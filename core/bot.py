import asyncio
import logging
import subprocess
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from core.bridge import send_message
from core.config import load_config
from core.session import SessionManager

logger = logging.getLogger(__name__)

_config: dict = {}
_sessions: SessionManager | None = None
_project_dir: str = "."


def _media_dir(chat_id: int) -> Path:
    d = Path(_project_dir) / "media" / str(chat_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_authorized(user_id: int, allowed: list[int]) -> bool:
    return user_id in allowed


async def _process_and_respond(update: Update, text: str) -> None:
    chat_id = update.effective_chat.id
    await update.message.chat.send_action(ChatAction.TYPING)

    session_id = _sessions.get_session(chat_id)
    response = await send_message(text, session_id=session_id, project_dir=_project_dir)

    if response.session_id:
        _sessions.set_session(chat_id, response.session_id)

    usage = response.usage or {}
    _sessions.log_usage(
        chat_id,
        cost_usd=response.cost_usd,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
    )

    # Split long messages (Telegram 4096 char limit)
    text = response.text
    while text:
        chunk, text = text[:4096], text[4096:]
        await update.message.reply_text(chunk)


async def _save_file(update: Update, context) -> tuple[Path, str] | None:
    """Download a photo or document from Telegram. Returns (path, description)."""
    chat_id = update.effective_chat.id
    msg = update.message
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if msg.photo:
        photo = msg.photo[-1]  # highest resolution
        file = await context.bot.get_file(photo.file_id)
        ext = ".jpg"
        name = f"photo_{ts}{ext}"
        desc = "photo"
    elif msg.document:
        doc = msg.document
        file = await context.bot.get_file(doc.file_id)
        name = doc.file_name or f"doc_{ts}"
        desc = f"document ({doc.mime_type or 'unknown type'})"
    elif msg.voice:
        voice = msg.voice
        file = await context.bot.get_file(voice.file_id)
        name = f"voice_{ts}.ogg"
        desc = f"voice message ({voice.duration}s)"
    elif msg.video:
        video = msg.video
        file = await context.bot.get_file(video.file_id)
        name = video.file_name or f"video_{ts}.mp4"
        desc = f"video ({video.duration}s)"
    elif msg.audio:
        audio = msg.audio
        file = await context.bot.get_file(audio.file_id)
        name = audio.file_name or f"audio_{ts}.mp3"
        desc = f"audio ({audio.duration}s)"
    else:
        return None

    path = _media_dir(chat_id) / name
    await file.download_to_drive(str(path))
    logger.info("Saved %s to %s", desc, path)
    return path, desc


async def handle_message(update: Update, context) -> None:
    if not is_authorized(update.effective_user.id, _config["telegram"]["allowed_users"]):
        await update.message.reply_text("You are not authorized to use this bot.")
        return
    await _process_and_respond(update, update.message.text)


async def handle_media(update: Update, context) -> None:
    if not is_authorized(update.effective_user.id, _config["telegram"]["allowed_users"]):
        await update.message.reply_text("You are not authorized to use this bot.")
        return

    result = await _save_file(update, context)
    if not result:
        await update.message.reply_text("Unsupported file type.")
        return

    path, desc = result
    caption = update.message.caption or ""

    # Tell Claude about the file so it can read it
    prompt = f"The user sent a {desc}, saved at: {path}"
    if caption:
        prompt += f"\nCaption: {caption}"
    prompt += "\nPlease look at/process this file and respond."

    await _process_and_respond(update, prompt)


async def handle_new(update: Update, context) -> None:
    if not is_authorized(update.effective_user.id, _config["telegram"]["allowed_users"]):
        await update.message.reply_text("You are not authorized to use this bot.")
        return
    _sessions.clear_session(update.effective_chat.id)
    await update.message.reply_text("Started a new conversation.")


async def handle_usage(update: Update, context) -> None:
    if not is_authorized(update.effective_user.id, _config["telegram"]["allowed_users"]):
        await update.message.reply_text("You are not authorized to use this bot.")
        return

    usage = _sessions.get_usage()
    today, total = usage["today"], usage["total"]

    def fmt(n: int) -> str:
        if n >= 1_000_000: return f"{n / 1_000_000:.1f}M"
        if n >= 1_000: return f"{n / 1_000:.1f}k"
        return str(n)

    await update.message.reply_text(
        f"Today: ${today['cost_usd']:.4f} | {today['messages']} msgs | "
        f"{fmt(today['input_tokens'])} in / {fmt(today['output_tokens'])} out\n"
        f"Total: ${total['cost_usd']:.4f} | {total['messages']} msgs | "
        f"{fmt(total['input_tokens'])} in / {fmt(total['output_tokens'])} out"
    )


async def handle_status(update: Update, context) -> None:
    if not is_authorized(update.effective_user.id, _config["telegram"]["allowed_users"]):
        await update.message.reply_text("You are not authorized to use this bot.")
        return
    sid = _sessions.get_session(update.effective_chat.id)
    await update.message.reply_text(f"Session: {sid or 'none'}")


async def handle_help(update: Update, context) -> None:
    await update.message.reply_text(
        "/new — New conversation\n"
        "/usage — Cost and token stats\n"
        "/status — Session info\n"
        "/help — This message"
    )


async def _heartbeat(project_dir: str, interval: int = 300) -> None:
    """Pull upstream every 5 min. Logs conflicts to memory/merge-conflicts.md."""
    while True:
        await asyncio.sleep(interval)
        try:
            remotes = (await asyncio.to_thread(
                subprocess.run, ["git", "remote"],
                cwd=project_dir, capture_output=True, text=True, timeout=10,
            )).stdout.strip().split("\n")
            remote = "upstream" if "upstream" in remotes else "origin"

            result = await asyncio.to_thread(
                subprocess.run, ["git", "pull", "--ff-only", remote, "main"],
                cwd=project_dir, capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and "Already up to date" not in result.stdout:
                logger.info("Heartbeat: pulled from %s", remote)
            elif result.returncode != 0:
                logger.warning("Heartbeat: pull failed — %s", result.stderr.strip())
                cf = Path(project_dir) / "memory" / "merge-conflicts.md"
                cf.parent.mkdir(parents=True, exist_ok=True)
                with open(cf, "a") as f:
                    f.write(f"\n## {datetime.now().isoformat()}\n")
                    f.write(f"Pull from `{remote}` failed:\n```\n{result.stderr.strip()}\n```\n")
        except Exception:
            logger.exception("Heartbeat failed")


def main():
    global _config, _sessions, _project_dir

    _project_dir = str(Path(__file__).resolve().parent.parent)
    _config = load_config()
    _sessions = SessionManager(Path(_project_dir) / "sessions.db")

    for subdir in ["daily", "chats"]:
        (Path(_project_dir) / "memory" / subdir).mkdir(parents=True, exist_ok=True)

    token = _config["telegram"]["token"]
    app = Application.builder().token(token).build()

    async def post_init(application):
        application.create_task(_heartbeat(_project_dir))
        for user_id in _config["telegram"]["allowed_users"]:
            try:
                await application.bot.send_message(user_id, "i'm back online 🦞")
            except Exception:
                logger.warning("Could not send startup message to %s", user_id)
    app.post_init = post_init

    app.add_handler(CommandHandler("new", handle_new))
    app.add_handler(CommandHandler("usage", handle_usage))
    app.add_handler(CommandHandler("status", handle_status))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("start", handle_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.ALL | filters.VOICE | filters.VIDEO | filters.AUDIO,
        handle_media,
    ))

    logger.info("Bot starting — allowed users: %s", _config["telegram"]["allowed_users"])
    app.run_polling()
