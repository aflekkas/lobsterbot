# lobsterbot

A 24/7 personal AI assistant on Telegram, powered by Claude Code.

Fork this repo, add your Telegram bot token, and you've got a personal AI assistant that can search the web, remember things about you, handle voice messages, photos, documents, and run on a schedule.

## Quick Start

```bash
git clone https://github.com/aflekkas/lobsterbot.git
cd lobsterbot
pip install -r requirements.txt
python scripts/setup_wizard.py   # or manually: cp -r user.example user && edit user/config.yaml
python run.py
```

## Getting a Telegram Bot Token

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the token into `user/config.yaml`

## Finding Your Telegram User ID

Message [@userinfobot](https://t.me/userinfobot) on Telegram — it will reply with your user ID.

## Requirements

- Python 3.11+
- Claude Code CLI (`claude`) installed and authenticated
- A Telegram bot token

### Optional

- `ffmpeg` + `faster-whisper` — for voice message transcription
- Node.js — for Playwright MCP (web browsing)

## Features

### Text Chat
Send messages and get AI-powered responses. Conversations persist via session management — the bot remembers context within a conversation.

### Voice Messages
Send voice messages — they're transcribed and processed as text. Requires `ffmpeg` and `faster-whisper`.

### Photos & Documents
Send photos or documents — Claude can see images and read files.

### Memory System
- **Daily logs** (`memory/daily/`) — the bot keeps a daily journal of notable events
- **User facts** (`memory/facts.md`) — persistent facts about you (name, preferences, etc.)
- **Chat summaries** (`memory/chats/`) — summaries of past conversations

### Agents
Built-in specialized agents for:
- **researcher** — web research with source citation
- **scheduler-agent** — daily planning, task tracking, reminders
- **writer** — drafting emails, docs, social media posts

### Scheduler
Proactive messaging via cron expressions. Configure in `user/config.yaml`:

```yaml
scheduler:
  tasks:
    - name: morning_brief
      cron: "0 8 * * *"
      prompt: "Good morning! Give me a brief overview of today."
      chat_id: 123456789
```

### Web Browsing
Playwright MCP server ships pre-configured for headless web browsing.

## Commands

- `/new` — Start a new conversation
- `/status` — Session info
- `/facts` — Show saved facts about you
- `/today` — Show today's daily log
- `/help` — Available commands

## Deployment (VPS)

One-command setup for Ubuntu:

```bash
./deploy/install.sh
```

This installs dependencies, sets up systemd services, and copies the config template. Then:

```bash
sudo systemctl enable --now claude-bot
sudo systemctl enable --now claude-scheduler  # optional
```

Update to latest:

```bash
./deploy/update.sh
```

## Architecture

```
Telegram → python-telegram-bot → MessageRouter (per-chat queue)
    → ProcessLock → claude -p --output-format json --resume SESSION_ID
    → Formatter → Telegram MarkdownV2 response
```

- **Thin bridge**: Messages go to Claude Code via subprocess (`claude -p`)
- **Session management**: SQLite maps Telegram chat IDs to Claude session IDs
- **Message queue**: Per-chat async queue prevents race conditions; batches rapid messages
- **Process lock**: File-based lock coordinates bot and scheduler processes
- **Permissions**: `.claude/settings.json` enforces a security boundary

## Project Structure

```
lobsterbot/
├── core/               # Framework code
│   ├── bot.py          # Telegram listener + handlers
│   ├── bridge.py       # Claude Code subprocess wrapper
│   ├── session.py      # SQLite session manager
│   ├── queue.py        # Per-chat message queue + process lock
│   ├── media.py        # Voice/photo/document handling
│   ├── formatter.py    # Markdown → Telegram formatting
│   ├── scheduler.py    # Cron-based proactive messaging
│   └── config.py       # YAML config loader
├── .claude/
│   ├── settings.json   # Permission boundary
│   └── agents/         # Specialized agents
├── memory/             # Bot's memory (gitignored contents)
├── user.example/       # Config template
├── deploy/             # VPS deployment scripts
├── scripts/            # Setup wizard
├── CLAUDE.md           # Bot personality + instructions
└── .mcp.json           # Playwright MCP config
```

## Fork Workflow

- `user/` and `memory/` contents are gitignored — your data stays local
- `user.example/` is the template — `install.sh` copies it to `user/`
- Framework updates in `core/`, `.claude/`, `deploy/` flow upstream cleanly
- `deploy/update.sh` pulls upstream, restarts services, never touches your config

## License

MIT
