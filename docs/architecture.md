# Architecture

## What lobster-bot Is

lobster-bot is a Telegram bot that acts as a personal AI assistant. It receives messages from Telegram, passes them to Claude Code (the CLI), and sends the response back. Claude Code runs with full system access, so the bot can read/write files, run shell commands, search the web, and use any tools on the server.

## Message Flow

```
User (Telegram) → python-telegram-bot → bot.py → bridge.py → claude CLI subprocess → Claude API
                                                                                        ↓
User (Telegram) ← bot.py (reply_text) ← bridge.py (parse JSON) ← claude CLI stdout (JSON) ←
```

Step by step:

1. **Receive**: `python-telegram-bot` receives the update via long polling (`app.run_polling()`).
2. **Auth**: `is_authorized()` checks the user's Telegram ID against `TELEGRAM_USER_IDS` from env.
3. **Route**: Slash commands (e.g. `/new`, `/help`) are handled directly by `core/commands.py` — Claude is not involved. Regular text messages and media go to Claude.
4. **Queue**: If Claude is already processing a message for this chat, new messages are queued in `_chat_queues[chat_id]` and combined into a single follow-up when Claude finishes.
5. **Bridge**: `bridge.py` spawns `claude -p <message> --output-format json --permission-mode dontAsk` as an async subprocess. If there is an active session, `--resume <session_id>` is added.
6. **Chat ID injection**: The user's message is prefixed with `[chat_id=XXXX]` so Claude can send live Telegram updates via `tools/telegram/send.sh`.
7. **Runtime context**: A temporary file is written to `runtime/<chat_id>.json` so hooks (like `telegram-notify.sh`) know which chat to notify. It is cleaned up after the subprocess finishes.
8. **Typing indicator**: While Claude works, `_keep_typing()` sends Telegram typing indicators every 4 seconds.
9. **Response**: Claude's JSON output is parsed. The `result` field becomes the reply text. `session_id`, `cost_usd`, and `usage` are extracted and stored.
10. **Split**: Telegram has a 4096 character limit per message. Long responses are split into chunks.
11. **Log**: Both user messages and assistant responses are logged to `sessions.db` (table `chat_log`). Usage is logged to `usage_log`.
12. **Cost check**: After each response, `_check_cost_alert()` compares daily spend against budget thresholds and sends alerts if crossed.

## Process Model

- The bot runs as a single Python process using `asyncio` (via `python-telegram-bot`'s `concurrent_updates=True`).
- Each message to Claude spawns a subprocess (`claude` CLI). Only one Claude process runs per chat at a time (enforced by `_chat_locks`).
- Multiple chats can have concurrent Claude processes.
- The Claude subprocess is tracked in `_active_procs[chat_id]` so `/cancel` can kill it.

## How Claude Code Is Invoked

```
claude -p "<message>" --output-format json --permission-mode dontAsk [--resume <session_id>]
```

- `-p` — pass the message as a prompt (non-interactive mode)
- `--output-format json` — get structured output with `result`, `session_id`, `cost_usd`, `usage`
- `--permission-mode dontAsk` — auto-approve all tool uses (controlled by `.claude/settings.json` allow list)
- `--resume` — continue an existing conversation session
- The `CLAUDECODE` env var is stripped from the subprocess environment to allow nested invocation.
- The working directory is the project root.

## Session Handling

- Each Telegram chat has at most one active Claude session (stored in `sessions.sessions` table).
- When Claude responds, its `session_id` is saved. The next message from that chat resumes the session.
- `/new` clears the session, starting a fresh conversation.
- Stale sessions (>24h) can be archived to `session_history` via `archive_stale()`.
- Past sessions can be resumed from `/history`.

## File Structure

```
lobster-bot/
├── run.py                    # Entry point — bootstrap + logging setup
├── core/
│   ├── bot.py                # Telegram handlers, media download, heartbeat, main()
│   ├── bridge.py             # Claude CLI subprocess wrapper, cancel support
│   ├── session.py            # SQLite session + usage + chat log manager
│   ├── config.py             # Load config from environment variables
│   └── commands.py           # Slash command handlers (no Claude involved)
├── CLAUDE.md                 # Personality, behavior rules, instructions for Claude
├── .claude/
│   ├── settings.json         # Permissions (tool allow list) and hooks config
│   ├── agents/               # Agent definitions (markdown with YAML frontmatter)
│   └── commands/             # Custom slash commands (markdown with frontmatter)
├── hooks/
│   ├── telegram-notify.sh    # PostToolUse hook — sends live updates to Telegram
│   └── session-end.sh        # Stop hook — stamps session end in daily log
├── tools/
│   └── telegram/
│       └── send.sh           # Send a Telegram message (used by Claude for live updates)
├── memory/
│   ├── facts.md              # Persistent facts about the user
│   └── daily/                # Daily activity logs (YYYY-MM-DD.md)
├── deploy/
│   ├── install.sh            # One-line installer
│   ├── update.sh             # Pull + restart
│   ├── autosync.sh           # Cron script: commit + push changes
│   └── systemd/
│       └── lobster-bot.service
├── user/
│   └── config.yaml           # Legacy config (not used by template — env vars instead)
├── media/                    # Downloaded photos/documents/voice (per chat_id)
├── logs/                     # Rotating log files (bot.log)
├── runtime/                  # Temporary per-chat context files (auto-cleaned)
├── sessions.db               # SQLite database (sessions, usage, chat log)
├── .env                      # Environment variables (gitignored)
└── .mcp.json                 # MCP server configuration (empty by default)
```

## Heartbeat

`_heartbeat()` runs as a background asyncio task. Every 5 minutes it does `git pull --ff-only origin main` to pick up changes pushed by autosync or manual commits. This means you can push code changes and they go live without restarting.

## Database Schema (sessions.db)

Four tables:

- **sessions** — One row per chat. Maps `chat_id` to current `session_id`. Updated on every Claude response.
- **session_history** — Archived sessions. When a session is cleared or archived, it moves here so it can be resumed later.
- **usage_log** — One row per Claude invocation. Tracks `cost_usd`, `input_tokens`, `output_tokens` per chat.
- **chat_log** — Every user message and assistant response, with timestamps. Used by `/history` and queryable via SQL.
