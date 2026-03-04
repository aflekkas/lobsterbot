# 🦞 lobster-bot

Your self-hosted AI assistant on Telegram. Powered by Claude Code.

It searches the web, remembers your conversations, and runs 24/7 on your own server.

## Get Started

```bash
git clone https://github.com/aflekkas/lobster-bot.git
cd lobster-bot
```

Create a `.env`:

```
TELEGRAM_TOKEN=your-token-from-botfather
TELEGRAM_USER_IDS=your-telegram-user-id
```

Run:

```bash
python run.py
```

The run script handles dependencies and loads your `.env` automatically.

## Setup

1. Get a bot token — message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`
2. Get your user ID — message [@userinfobot](https://t.me/userinfobot)
3. Put both in `.env`

## What It Can Do

- **Web search** — finds and summarizes info from the web
- **Persistent memory** — remembers facts about you and keeps daily logs
- **Conversations that stick** — sessions persist, so context carries across messages
- **Usage tracking** — know exactly what you're spending with `/usage`
- **Auto-updates** — pulls from git every 5 minutes, push a change and it goes live

## Deploy on a VPS

One command:

```bash
curl -sSL https://raw.githubusercontent.com/aflekkas/lobster-bot/main/deploy/install.sh | bash
```

Then authenticate Claude Code (`claude`), edit your `.env`, and enable the service:

```bash
systemctl enable --now lobster-bot
```

## Requirements

- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)

---

If this is useful to you, a ⭐ on the repo goes a long way.
