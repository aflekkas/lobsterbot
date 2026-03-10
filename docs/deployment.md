# Deployment

## System Requirements

- **Python 3.11+** (for `X | Y` type union syntax)
- **Node.js 18+** (required by Claude Code CLI)
- **Claude Code CLI** (`npm i -g @anthropic-ai/claude-code`) — must be authenticated (`claude` first run)
- **python-telegram-bot 21+** (installed via `requirements.txt`)
- A Telegram bot token from @BotFather
- Your Telegram user ID (get from @userinfobot)
- A VPS or always-on machine

## Quick Install

```bash
curl -sSL https://raw.githubusercontent.com/aflekkas/lobster-bot/main/deploy/install.sh | bash
```

This script:
1. Installs Python, Node.js, and Claude Code CLI if missing
2. Clones the repo to `~/lobster-bot` (or `$LOBSTERBOT_DIR`)
3. Installs Python dependencies
4. Creates a `.env` template
5. Copies the systemd service file

## Manual Setup

```bash
git clone https://github.com/aflekkas/lobster-bot.git ~/lobster-bot
cd ~/lobster-bot
pip install -r requirements.txt
```

Create `.env`:
```
TELEGRAM_TOKEN=your-token-from-botfather
TELEGRAM_USER_IDS=your-telegram-user-id
```

Authenticate Claude Code (first time only):
```bash
claude
```

## Running

### Foreground (for testing)
```bash
cd ~/lobster-bot
python3 run.py
```

`run.py` handles everything: loads `.env`, checks dependencies, sets up logging, starts the bot.

### Systemd Service

Copy the service file:
```bash
sudo cp deploy/systemd/lobster-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lobster-bot
```

The service file (`deploy/systemd/lobster-bot.service`):
- Runs as root (change `User=` if needed)
- Working directory: project root
- Loads `.env` via `EnvironmentFile`
- Auto-restarts on crash (10 second delay)
- Sets `PYTHONUNBUFFERED=1` for real-time log output

Commands:
```bash
systemctl start lobster-bot
systemctl stop lobster-bot
systemctl restart lobster-bot
systemctl status lobster-bot
```

## Autosync (Git Backup)

`deploy/autosync.sh` commits and pushes all local changes to git. Set it up on a cron:

```bash
crontab -e
# Add:
*/5 * * * * /root/lobster-bot/deploy/autosync.sh >> /root/lobster-bot/logs/autosync.log 2>&1
```

This runs every 5 minutes. It:
1. Checks for uncommitted changes (including untracked files)
2. Stages everything (`git add -A`)
3. Commits with a UTC timestamp message
4. Pushes to origin/main

This ensures memory files, config changes, and anything Claude creates are backed up.

## Updating

Pull latest and restart:
```bash
./deploy/update.sh
```

Or manually:
```bash
cd ~/lobster-bot
git pull --ff-only
pip install -r requirements.txt --quiet
systemctl restart lobster-bot
```

The bot also auto-pulls every 5 minutes via the heartbeat task (built into bot.py). So pushing changes to git makes them go live without manual restart.

## Logs

### Application logs
Written to `logs/bot.log` via Python's `RotatingFileHandler`:
- Max 5MB per file, 3 backup files
- Also printed to stdout/stderr (visible in journalctl)

### Live logs
```bash
journalctl -u lobster-bot -f
```

### View from Telegram
Use `/logs` to browse log files and filter for errors.

### What gets logged
- Bot startup and allowed users
- Every message received (user ID)
- Media downloads (file type, path)
- Heartbeat pulls (only when changes are pulled or errors occur)
- Errors and exceptions with full tracebacks
- `httpx` logging is suppressed (set to WARNING) to reduce noise

## Debugging

### Bot won't start
- Check `.env` exists and has `TELEGRAM_TOKEN` and `TELEGRAM_USER_IDS`
- Check `claude` CLI is installed and authenticated: `which claude && claude --version`
- Check Python deps: `python3 -c "import telegram"`
- Check logs: `journalctl -u lobster-bot --no-pager -n 50`

### Claude not responding
- Check if a process is stuck: `ps aux | grep claude`
- Use `/cancel` to kill a stuck process
- Use `/new` to start a fresh session (old session may be corrupted)
- Check `.claude/settings.json` permissions — if a tool is denied, Claude may hang

### Messages not being sent
- Verify your user ID is in `TELEGRAM_USER_IDS`
- Check the bot token is valid: `curl https://api.telegram.org/bot<TOKEN>/getMe`
- Long messages are split at 4096 chars — check if the response is just empty

### Hooks not firing
- Verify hooks are configured in `.claude/settings.json` under `hooks`
- Check hook scripts are executable: `chmod +x hooks/*.sh`
- Check `runtime/` directory exists (created by bridge.py)
- Test hooks manually: `echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | bash hooks/telegram-notify.sh`

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_TOKEN` | Yes | Bot token from @BotFather |
| `TELEGRAM_USER_IDS` | Yes | Comma-separated Telegram user IDs allowed to use the bot |
| `ANTHROPIC_API_KEY` | Depends | Required if Claude CLI is not authenticated via `claude` command |

All other env vars are optional and depend on which tools you add (OPENAI_API_KEY, etc.). Put them all in `.env`.
