#!/usr/bin/env bash
set -euo pipefail

# 🦞 lobster-bot installer
# Usage: curl -sSL https://raw.githubusercontent.com/aflekkas/lobster-bot/main/deploy/install.sh | bash

REPO_DIR="${LOBSTERBOT_DIR:-$HOME/lobster-bot}"

echo ""
echo "  🦞 lobster-bot installer"
echo ""

# ── Install Python if missing ──
if ! command -v python3 >/dev/null 2>&1; then
    echo "Installing Python..."
    sudo apt-get update && sudo apt-get install -y python3 python3-pip
fi

# ── Install Node.js if missing (needed for Claude Code CLI) ──
if ! command -v node >/dev/null 2>&1; then
    echo "Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

# ── Install Claude Code CLI if missing ──
if ! command -v claude >/dev/null 2>&1; then
    echo "Installing Claude Code CLI..."
    npm i -g @anthropic-ai/claude-code
fi

# ── Clone or update repo ──
if [ -d "$REPO_DIR" ]; then
    echo "Updating $REPO_DIR..."
    cd "$REPO_DIR" && git pull --ff-only
else
    echo "Cloning lobster-bot..."
    git clone https://github.com/aflekkas/lobster-bot.git "$REPO_DIR"
    cd "$REPO_DIR"
fi

# ── Install Python deps ──
python3 -m pip install -r requirements.txt -q

# ── Create .env if missing ──
if [ ! -f "$REPO_DIR/.env" ]; then
    cat > "$REPO_DIR/.env" << 'EOF'
TELEGRAM_TOKEN=your-token-from-botfather
TELEGRAM_USER_IDS=your-telegram-user-id
EOF
fi

# ── Set up systemd ──
if command -v systemctl >/dev/null 2>&1; then
    sudo cp "$REPO_DIR/deploy/systemd/lobster-bot.service" /etc/systemd/system/
    sudo sed -i "s|/root/lobster-bot|$REPO_DIR|g" /etc/systemd/system/lobster-bot.service
    sudo sed -i "s|User=root|User=$(whoami)|g" /etc/systemd/system/lobster-bot.service
    sudo systemctl daemon-reload
fi

echo ""
echo "  ✅ Installed to $REPO_DIR"
echo ""
echo "  Next steps:"
echo "    1. Run 'claude' to authenticate (first time only)"
echo "    2. Edit $REPO_DIR/.env with your Telegram token and user ID"
echo "    3. systemctl enable --now lobster-bot"
echo ""
