# Customization

## CLAUDE.md — Personality and Behavior

`CLAUDE.md` in the project root is the system prompt for every Claude invocation. It controls:

- **Tone**: How Claude talks (casual, formal, emoji usage, message length)
- **Permissions**: What Claude is allowed to do on the system
- **Live updates**: When and how Claude sends progress notifications
- **Memory instructions**: Which files to read at conversation start, where to save facts
- **Orchestration**: Whether Claude should delegate to agents or handle tasks directly

Edit this file to change your bot's personality. Changes take effect on the next message (no restart needed — Claude reads CLAUDE.md fresh each invocation).

## Environment Variables (.env)

The `.env` file at the project root is loaded by `run.py` at startup and by `deploy/systemd/lobster-bot.service` via `EnvironmentFile`.

Required:
```
TELEGRAM_TOKEN=your-token-from-botfather
TELEGRAM_USER_IDS=comma-separated-user-ids
```

Optional (add as needed for tools):
```
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...    # If not using claude auth
```

Config is loaded by `core/config.py` from environment variables. The `user/config.yaml` file exists but is not used by the config loader — environment variables are the source of truth.

## Adding Tools

Tools live in `tools/<tool-name>/` directories. Each tool directory should have:
- A shared client module (e.g. `client.js`, `client.py`)
- CLI scripts for specific actions
- A `README.md` describing usage

Never put scripts directly in `tools/` root — always use subdirectories.

Claude discovers tools by reading the `tools/` directory structure. You can tell Claude about new tools by mentioning them in CLAUDE.md or memory/facts.md. The `/tools` command lets you browse them from Telegram.

The only built-in tool is `tools/telegram/send.sh` for sending Telegram messages. All other tools are user-added.

## Adding Agents

Create a `.md` file in `.claude/agents/` with YAML frontmatter:

```
---
name: my-agent
model: sonnet          # optional, defaults to Claude's default
maxTurns: 15           # optional, limits agent iterations
---

# Agent Name

Description and detailed instructions for the agent.

## What this agent does
...

## Guidelines
...
```

The agent becomes available to Claude for delegation and appears in the `/agents` command.

Frontmatter fields:
- `name` — identifier (matches filename stem)
- `model` — which Claude model to use (sonnet, opus, haiku)
- `maxTurns` — maximum tool-use turns before the agent must stop

Write agent instructions as if briefing a new employee — include everything they need to know: file paths, tool commands, expected outputs, common gotchas.

## Adding Custom Commands

Create a `.md` file in `.claude/commands/`:

```
---
description: What this command does (shown in Telegram command list)
---

The prompt that gets sent to Claude when someone uses this command.
You can write multi-line instructions here.
```

The filename becomes the command name: `summarize.md` creates `/summarize`.

When the user types `/summarize <args>`, Claude receives:
```
[Command: /summarize]

<prompt body from the file>

User input: <args>
```

Reserved names that cannot be used: new, cancel, history, memory, tools, agents, logs, status, repo, restart, help, start.

Custom commands are discovered at bot startup. Restart the bot after adding new ones.

## Adding Hooks

Hooks are configured in `.claude/settings.json` under the `hooks` key. They are shell scripts that Claude Code runs at specific lifecycle points.

### Hook types

**PostToolUse** — runs after Claude uses a tool. Receives JSON on stdin with `tool_name` and `tool_input`. Use `matcher` to filter which tools trigger it.

**Stop** — runs when Claude finishes processing (the subprocess exits).

### Configuration format

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash|WebSearch|WebFetch|Edit|Write",
        "hooks": [{ "type": "command", "command": "bash hooks/my-hook.sh" }]
      }
    ],
    "Stop": [
      {
        "hooks": [{ "type": "command", "command": "bash hooks/cleanup.sh" }]
      }
    ]
  }
}
```

Hook scripts should:
- Be executable (`chmod +x`)
- Exit 0 on success
- Read JSON from stdin for PostToolUse hooks
- Be fast (they run synchronously in the Claude process)

### Built-in hooks

- `hooks/telegram-notify.sh` — PostToolUse hook that sends live tool-use updates to the user's Telegram chat
- `hooks/session-end.sh` — Stop hook that stamps "session ended" in today's daily log

## MCP Servers

`.mcp.json` in the project root configures Model Context Protocol servers. By default it is empty:

```json
{
  "mcpServers": {}
}
```

Add MCP servers to give Claude access to external services (Gmail, Google Calendar, Notion, databases, etc.). Each server needs a matching permission in `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "mcp__my_server__*"
    ]
  }
}
```

## Permissions (.claude/settings.json)

The `permissions.allow` list controls which tools Claude can use without asking. The template ships with:

```json
{
  "allow": [
    "Read", "Glob", "Grep",
    "WebSearch", "WebFetch(*)",
    "Write", "Edit",
    "Bash(*)"
  ]
}
```

This gives Claude full access. To restrict, remove entries or add to `permissions.deny`.

## Memory System

### memory/facts.md
Long-lived facts. Claude reads this at conversation start and writes to it when it learns something important. Put things here like: timezone, name, preferences, project context, API endpoints, recurring workflows.

### memory/daily/YYYY-MM-DD.md
Daily logs. The bridge auto-appends conversation summaries. Claude also writes to these manually for notable events. The Stop hook stamps session end times. These files accumulate over time — old ones are not deleted.

### Customizing memory behavior
The memory instructions are in CLAUDE.md. You can change what Claude reads at startup, where it saves things, or add new memory files (e.g. `memory/projects/` for per-project context).

## Daily Budget

Set `DAILY_BUDGET` in `core/bot.py` to your preferred daily spend limit in USD. Alert thresholds are at 50%, 80%, and 100%. Alerts are sent as Telegram messages. The budget is advisory — it does not block Claude from responding after the limit is reached.
