#!/usr/bin/env bash
set -euo pipefail

# Switch statusline between full (3-line) and compact (1-line) modes.
# Usage:
#   claude-ui-mode full      # 3-line statusline
#   claude-ui-mode compact   # 1-line statusline
#   claude-ui-mode           # show current mode

INSTALL_DIR="${CLAUDE_UI_HOME:-$HOME/.claude-ui}"
SETTINGS_FILE="$HOME/.claude/settings.json"

GREEN='\033[92m'
CYAN='\033[96m'
YELLOW='\033[93m'
RED='\033[91m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

if [ ! -f "$SETTINGS_FILE" ]; then
    echo -e "${RED}✗${RESET} $SETTINGS_FILE not found"
    exit 1
fi

# Resolve real install dir (follows symlinks)
REAL_DIR="$(readlink -f "$INSTALL_DIR" 2>/dev/null || realpath "$INSTALL_DIR" 2>/dev/null || echo "$INSTALL_DIR")"

show_current() {
    current=$(python3 -c "
import json
with open('$SETTINGS_FILE') as f:
    s = json.load(f)
cmd = s.get('statusLine', {}).get('command', '')
print('compact' if '--compact' in cmd else 'full')
")
    echo -e "  Current mode: ${BOLD}${CYAN}${current}${RESET}"
    echo ""
    echo -e "  ${DIM}Usage: claude-ui-mode [full|compact]${RESET}"
}

set_mode() {
    local mode="$1"
    python3 << PYEOF
import json

mode = "$mode"
settings_file = "$SETTINGS_FILE"
real_dir = "$REAL_DIR"

with open(settings_file) as f:
    settings = json.load(f)

base_cmd = f"python3 {real_dir}/claude-code-statusline/statusline.py"
if mode == "compact":
    cmd = f"{base_cmd} --compact"
else:
    cmd = base_cmd

settings["statusLine"] = {
    "type": "command",
    "command": cmd,
}

with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
PYEOF
    echo -e "  ${GREEN}✓${RESET} Statusline mode: ${BOLD}${CYAN}${mode}${RESET}"
    echo -e "  ${DIM}Restart Claude Code for changes to take effect.${RESET}"
}

case "${1:-}" in
    full)
        set_mode "full"
        ;;
    compact)
        set_mode "compact"
        ;;
    "")
        show_current
        ;;
    *)
        echo -e "  ${RED}✗${RESET} Unknown mode: $1"
        echo -e "  ${DIM}Usage: claude-ui-mode [full|compact]${RESET}"
        exit 1
        ;;
esac
