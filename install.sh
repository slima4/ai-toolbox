#!/usr/bin/env bash
set -euo pipefail

# ── Claude UI Installer ─────────────────────────────────────────────
# Installs the full ai-toolbox suite for Claude Code:
#   • Statusline — real-time status bar
#   • Hooks — file hotspots, dependency warnings, churn alerts
#   • Commands — /ui:session, /ui:cost, /ui:perf, /ui:context
#   • Monitor — live dashboard (standalone terminal tool)
#   • Session Stats — post-session analytics
#   • Session Manager — browse, compare, export sessions
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/slima4/ai-toolbox/main/install.sh | bash
#   # or
#   git clone https://github.com/slima4/ai-toolbox.git && ./ai-toolbox/install.sh

REPO_URL="https://github.com/slima4/ai-toolbox.git"
INSTALL_DIR="${CLAUDE_UI_HOME:-$HOME/.claude-ui}"
CLAUDE_DIR="$HOME/.claude"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
COMMANDS_DIR="$CLAUDE_DIR/commands"
BIN_DIR="$HOME/.local/bin"

# Colors
RED='\033[91m'
GREEN='\033[92m'
YELLOW='\033[93m'
CYAN='\033[96m'
MAGENTA='\033[95m'
DIM='\033[2m'
BOLD='\033[1m'
RESET='\033[0m'

print_header() {
    echo ""
    echo -e "${GREEN}${BOLD}  ╔══════════════════════════════════════╗${RESET}"
    echo -e "${GREEN}${BOLD}  ║         Claude UI Installer          ║${RESET}"
    echo -e "${GREEN}${BOLD}  ╚══════════════════════════════════════╝${RESET}"
    echo ""
}

step() {
    echo -e "  ${CYAN}▶${RESET} $1"
}

ok() {
    echo -e "  ${GREEN}✓${RESET} $1"
}

warn() {
    echo -e "  ${YELLOW}!${RESET} $1"
}

fail() {
    echo -e "  ${RED}✗${RESET} $1"
    exit 1
}

# ── Preflight checks ────────────────────────────────────────────────

print_header

step "Checking requirements..."

# Python 3.8+
if ! command -v python3 &>/dev/null; then
    fail "python3 not found. Install Python 3.8+ first."
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]; }; then
    fail "Python 3.8+ required, found $PY_VERSION"
fi
ok "Python $PY_VERSION"

# Git
if ! command -v git &>/dev/null; then
    fail "git not found. Install git first."
fi
ok "git $(git --version | awk '{print $3}')"

# Claude Code directory
if [ ! -d "$CLAUDE_DIR" ]; then
    fail "$CLAUDE_DIR not found. Install Claude Code first: https://claude.ai/code"
fi
ok "Claude Code detected"

# ── Download / Update ────────────────────────────────────────────────

echo ""
if [ -d "$INSTALL_DIR/.git" ]; then
    step "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull --quiet origin main 2>/dev/null || warn "Could not pull latest (offline?)"
    ok "Updated $INSTALL_DIR"
else
    # Check if we're running from inside the repo already
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "$SCRIPT_DIR/claude-code-statusline/statusline.py" ]; then
        # Running from repo — symlink instead of clone
        step "Linking from local repo..."
        if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
            ln -sfn "$SCRIPT_DIR" "$INSTALL_DIR"
            ok "Linked $INSTALL_DIR → $SCRIPT_DIR"
        else
            ok "Already at $INSTALL_DIR"
        fi
    else
        step "Cloning repository..."
        git clone --quiet "$REPO_URL" "$INSTALL_DIR"
        ok "Cloned to $INSTALL_DIR"
    fi
fi

# ── Install slash commands ───────────────────────────────────────────

echo ""
step "Installing slash commands..."

mkdir -p "$COMMANDS_DIR"

# Symlink the ui commands directory
if [ -L "$COMMANDS_DIR/ui" ]; then
    rm "$COMMANDS_DIR/ui"
fi
if [ -d "$COMMANDS_DIR/ui" ]; then
    warn "Existing $COMMANDS_DIR/ui/ directory found — backing up"
    mv "$COMMANDS_DIR/ui" "$COMMANDS_DIR/ui.backup.$(date +%s)"
fi
ln -sfn "$INSTALL_DIR/claude-code-commands/ui" "$COMMANDS_DIR/ui"
ok "/ui:session, /ui:cost, /ui:perf, /ui:context"

# ── Configure settings.json ─────────────────────────────────────────

echo ""
step "Configuring Claude Code settings..."

# Use Python to safely merge into settings.json
python3 << 'PYEOF'
import json
import os
import sys
from pathlib import Path

settings_file = os.path.expanduser("~/.claude/settings.json")
install_dir = os.environ.get("INSTALL_DIR", os.path.expanduser("~/.claude-ui"))

# Load existing settings
settings = {}
if os.path.exists(settings_file):
    try:
        with open(settings_file) as f:
            settings = json.load(f)
    except (json.JSONDecodeError, IOError):
        # Backup corrupted file
        backup = settings_file + ".backup"
        if os.path.exists(settings_file):
            os.rename(settings_file, backup)
            print(f"  \033[93m!\033[0m Backed up corrupted settings to {backup}")

# Resolve install_dir if it's a symlink
real_dir = os.path.realpath(install_dir)

# ── Statusline ──
statusline_cmd = f"python3 {real_dir}/claude-code-statusline/statusline.py"
current_sl = settings.get("statusLine", {})
if current_sl.get("command") != statusline_cmd:
    settings["statusLine"] = {
        "type": "command",
        "command": statusline_cmd,
    }
    print(f"  \033[92m✓\033[0m Statusline configured")
else:
    print(f"  \033[92m✓\033[0m Statusline already configured")

# ── Hooks ──
hooks = settings.get("hooks", {})

hook_configs = [
    {
        "event": "SessionStart",
        "matcher": "",
        "command": f"python3 {real_dir}/claude-code-hooks/session-heatmap.py",
        "label": "SessionStart → file hotspots",
    },
    {
        "event": "PreToolUse",
        "matcher": "Edit|Write",
        "command": f"python3 {real_dir}/claude-code-hooks/pre-edit-churn.py",
        "label": "PreToolUse → churn warnings",
    },
    {
        "event": "PostToolUse",
        "matcher": "Edit|Write",
        "command": f"python3 {real_dir}/claude-code-hooks/post-edit-deps.py",
        "label": "PostToolUse → dependency check",
    },
]

for cfg in hook_configs:
    event = cfg["event"]
    if event not in hooks:
        hooks[event] = []

    # Check if hook already exists
    already_exists = False
    for rule in hooks[event]:
        for h in rule.get("hooks", []):
            if h.get("command") == cfg["command"]:
                already_exists = True
                break
        if already_exists:
            break

    if not already_exists:
        hooks[event].append({
            "matcher": cfg["matcher"],
            "hooks": [{"type": "command", "command": cfg["command"]}],
        })
        print(f"  \033[92m✓\033[0m {cfg['label']}")
    else:
        print(f"  \033[92m✓\033[0m {cfg['label']} (already configured)")

settings["hooks"] = hooks

# Write settings
Path(settings_file).parent.mkdir(parents=True, exist_ok=True)
with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
PYEOF

# ── Install CLI commands ─────────────────────────────────────────────

echo ""
step "Installing CLI tools..."

mkdir -p "$BIN_DIR"

# Create wrapper scripts
cat > "$BIN_DIR/claude-monitor" << EOF
#!/usr/bin/env bash
exec python3 "$INSTALL_DIR/claude-code-monitor/monitor.py" "\$@"
EOF
chmod +x "$BIN_DIR/claude-monitor"
ok "claude-monitor"

cat > "$BIN_DIR/claude-stats" << EOF
#!/usr/bin/env bash
exec python3 "$INSTALL_DIR/claude-code-session-stats/session-stats.py" "\$@"
EOF
chmod +x "$BIN_DIR/claude-stats"
ok "claude-stats"

cat > "$BIN_DIR/claude-sessions" << EOF
#!/usr/bin/env bash
exec python3 "$INSTALL_DIR/claude-code-session-manager/session-manager.py" "\$@"
EOF
chmod +x "$BIN_DIR/claude-sessions"
ok "claude-sessions"

cat > "$BIN_DIR/claude-ui-uninstall" << EOF
#!/usr/bin/env bash
exec bash "$INSTALL_DIR/uninstall.sh" "\$@"
EOF
chmod +x "$BIN_DIR/claude-ui-uninstall"
ok "claude-ui-uninstall"

# Check if BIN_DIR is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not in your PATH"
    echo ""
    echo -e "  Add to your shell profile:"
    echo -e "  ${DIM}echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc${RESET}"
fi

# ── Summary ──────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}${BOLD}  ╔══════════════════════════════════════╗${RESET}"
echo -e "${GREEN}${BOLD}  ║       Installation Complete!         ║${RESET}"
echo -e "${GREEN}${BOLD}  ╚══════════════════════════════════════╝${RESET}"
echo ""
echo -e "  ${BOLD}What's installed:${RESET}"
echo ""
echo -e "  ${CYAN}Statusline${RESET}      Real-time status bar in Claude Code"
echo -e "  ${CYAN}Hooks${RESET}           File hotspots, dependency warnings, churn alerts"
echo -e "  ${CYAN}Commands${RESET}        /ui:session  /ui:cost  /ui:perf  /ui:context"
echo -e "  ${CYAN}Monitor${RESET}         claude-monitor (live dashboard in separate terminal)"
echo -e "  ${CYAN}Stats${RESET}           claude-stats (post-session analytics)"
echo -e "  ${CYAN}Sessions${RESET}        claude-sessions (browse, compare, export)"
echo ""
echo -e "  ${BOLD}Quick start:${RESET}"
echo ""
echo -e "  ${DIM}# Start Claude Code — statusline and hooks are automatic${RESET}"
echo -e "  claude"
echo ""
echo -e "  ${DIM}# Open a second terminal for the live monitor${RESET}"
echo -e "  claude-monitor"
echo ""
echo -e "  ${DIM}# Inside Claude Code, use slash commands${RESET}"
echo -e "  /ui:session    ${DIM}# full session report${RESET}"
echo -e "  /ui:cost       ${DIM}# cost deep dive${RESET}"
echo ""
echo -e "  ${DIM}# Post-session analytics${RESET}"
echo -e "  claude-stats"
echo -e "  claude-sessions list"
echo ""
echo -e "  ${DIM}Installed to: $INSTALL_DIR${RESET}"
echo -e "  ${DIM}To update:    cd $INSTALL_DIR && git pull${RESET}"
echo -e "  ${DIM}To uninstall: claude-ui-uninstall${RESET}"
echo ""
