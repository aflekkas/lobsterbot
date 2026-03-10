# Features

## Message Handling

### Text Messages
Any non-command text message is forwarded to Claude Code. The message is prefixed with `[chat_id=XXXX]` so Claude can send live updates. If Claude is already processing a message for this chat, the new message is queued and delivered as a combined follow-up when Claude finishes.

### Photos
Photos are downloaded to `media/<chat_id>/photo_<timestamp>.jpg`. Claude receives: "The user sent a photo, saved at: <path>". Captions are included if present. Claude can read the image (it is multimodal).

### Documents
Documents are downloaded to `media/<chat_id>/<filename>`. Claude receives the path, MIME type, and any caption. This works for PDFs, code files, spreadsheets, etc.

### Voice Messages
Voice messages are downloaded as `.ogg` files to `media/<chat_id>/voice_<timestamp>.ogg`. They are not transcribed in the template (the Whisper integration in the personal instance is optional). Claude receives the file path and duration.

### Video and Audio
Videos and audio files are downloaded to `media/<chat_id>/` and Claude receives the path, duration, and any caption.

## Built-in Commands

All slash commands are handled directly by `core/commands.py` — they do not invoke Claude. They respond instantly.

### /new
Clears the current Claude session for this chat. The next message starts a fresh conversation with no prior context.

### /cancel
Kills the running Claude subprocess for this chat (via `proc.kill()`). Returns "cancelled" if something was running, "nothing running to cancel" otherwise.

### /history
Shows an inline keyboard with options:
- **Today** / **Yesterday** / **Last 7 days** — shows recent chat messages from `chat_log`
- **Past sessions** — lists archived sessions with "Resume" buttons to restore a previous conversation

### /memory
Shows an inline keyboard to browse the memory system:
- **Facts** — shows `memory/facts.md`
- **Today's log** / **Yesterday** — shows daily logs
- **List daily logs** — lists the 10 most recent daily log files

### /tools
Lists all subdirectories in `tools/`. Tapping a tool shows its script count, with buttons to view its README or list its scripts.

### /agents
Lists all `.md` files in `.claude/agents/`. Shows agent name and first line description. Tapping shows the full agent definition.

### /logs
Lists log files in `logs/`. Tapping shows the last 30 lines. Also has an "Errors only" button that filters for ERROR and WARNING lines in `bot.log`.

### /status
Shows the current Claude session ID for this chat (or "none" if no active session).

### /repo
Shows an inline keyboard with git operations:
- **Status** — `git status --short`
- **Recent commits** — `git log --oneline -15`
- **Branch** — `git branch -a`
- **Remotes** — `git remote -v`
- **Diff (staged)** — `git diff --cached --stat`

### /restart
Sends "restarting..." then runs `systemctl restart lobster-bot`. The bot comes back up and sends "i'm back online" to all allowed users.

### /help
Lists all available commands with descriptions. Also aliased to /start (for new Telegram conversations).

## Custom Commands

You can create custom slash commands by adding `.md` files to `.claude/commands/`. Each file becomes a Telegram command.

File format:
```
---
description: Short description shown in Telegram command list
---

The prompt body that gets sent to Claude when the user runs this command.
```

Example: `.claude/commands/weather.md` creates a `/weather` command. When the user types `/weather London`, Claude receives the prompt body plus "User input: London".

Custom commands are discovered at startup. They cannot conflict with reserved command names (new, cancel, history, memory, tools, agents, logs, status, repo, restart, help, start).

## Memory System

### memory/facts.md
Persistent facts about the user. Claude reads this at the start of every conversation and writes to it when it learns something important. Things like timezone, preferences, project context.

### memory/daily/YYYY-MM-DD.md
Daily activity logs. Claude reads today's and yesterday's logs at conversation start. The bridge automatically appends conversation summaries (user message + bot response) to today's log after each exchange. The `session-end.sh` hook stamps "session ended" when Claude finishes.

### sessions.db — chat_log table
Every user message and assistant response is automatically logged with timestamps. Query with:
```sql
SELECT * FROM chat_log WHERE chat_id = ? ORDER BY timestamp DESC LIMIT 50
```

## Live Updates (Hooks)

### PostToolUse — telegram-notify.sh
Configured in `.claude/settings.json`. After Claude uses Bash, WebSearch, WebFetch, Edit, or Write, this hook sends a short notification to the user's Telegram chat. Messages are contextual:
- Bash: "running: <command>"
- WebSearch: "searching: <query>"
- WebFetch: "fetching: <url>"
- Edit/Write: "writing: <filepath>"
- Other tools: "using: <tool_name>"

The hook reads the active chat_id from `runtime/<chat_id>.json` (written by bridge.py before spawning Claude, cleaned up after).

### Stop — session-end.sh
When Claude finishes (the subprocess exits), this hook appends "session ended HH:MM" to today's daily log.

### How hooks work
Hooks are configured in `.claude/settings.json` under the `hooks` key. Claude Code calls them as shell commands, passing tool info as JSON on stdin. See `.claude/settings.json` for the exact config.

## Live Updates (Manual)

Claude can also send updates manually during its work by calling:
```bash
bash tools/telegram/send.sh <chat_id> "message"
```
The `[chat_id=XXXX]` prefix on every message tells Claude which chat to update. CLAUDE.md instructs Claude to send updates within 5 seconds of starting, and every 15-30 seconds during long tasks.

## Session Management

- Each chat gets one Claude session. Sessions persist across messages (Claude remembers the conversation).
- `/new` clears the session (fresh start).
- `/history > Past sessions` lets you resume old sessions.
- Sessions are stored in SQLite (`sessions` table). Old sessions move to `session_history` when archived.
- The `--resume <session_id>` flag on the Claude CLI is what enables conversation continuity.

## Cost Tracking and Budget Alerts

- Every Claude invocation logs `cost_usd`, `input_tokens`, `output_tokens` to the `usage_log` table.
- The daily budget is set in `bot.py` (`DAILY_BUDGET = 5.00` USD by default).
- Alert thresholds are at 50%, 80%, and 100% of the daily budget.
- When a threshold is crossed, the bot sends a cost alert message to the chat.
- `/status` can be extended to show usage stats (the `get_usage()` method is already available).

## Autosync

`deploy/autosync.sh` is meant to run on a cron schedule (e.g. every 5 minutes). It:
1. Fetches upstream (non-destructive)
2. Checks for local changes (modified files, untracked files)
3. Stages everything, commits with timestamp message
4. Pushes to origin/main

This ensures that files Claude creates or modifies (memory logs, config changes, new tools) are backed up to git automatically.

## Agents

Claude can delegate tasks to specialized sub-agents. These are defined in `.claude/agents/` as markdown files with YAML frontmatter:

```
---
name: researcher
model: sonnet
maxTurns: 15
---

# Agent description and instructions here
```

Built-in agents:
- **researcher** — Web research (WebSearch + WebFetch). Cites sources, synthesizes from multiple results.
- **writer** — Drafts emails, posts, documents. Reads memory for user context.
- **scheduler-agent** — Daily planning, tasks, reminders. Reads/writes daily logs.

The orchestrator pattern (described in CLAUDE.md) tells Claude to delegate to agents rather than doing long-running work itself, staying responsive to the user.

## Process Cancellation

- `/cancel` calls `cancel_chat(chat_id)` which does `proc.kill()` on the active Claude subprocess.
- The killed process returns a negative return code, which bridge.py detects and returns a "cancelled" response.
- The bot logs "(cancelled)" to chat_log but does not send "cancelled" as a Telegram reply.
