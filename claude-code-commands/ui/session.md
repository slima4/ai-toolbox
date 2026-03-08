---
description: Deep session analysis — context breakdown, cost details, token consumers, compaction prediction
allowed-tools: Bash
---

Run the session report script and present the output to the user. Do not add commentary — just show the report.

```bash
python3 "$(dirname "$(readlink -f ~/.claude/commands/ui/session.md)" 2>/dev/null || echo "SCRIPT_DIR")/session_report.py"
```

If the above path fails, try:

```bash
python3 ~/.claude/commands/ui/session_report.py
```

Show the output as-is in a code block. If there are interesting findings (unusual cost spikes, high error rates, approaching compaction), add a brief 1-2 sentence summary after the report.
