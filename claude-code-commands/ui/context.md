---
description: Context window deep dive — usage curve, growth rate, compaction timeline, remaining capacity
allowed-tools: Bash
---

Run the context report script and present the output to the user. Do not add commentary — just show the report.

```bash
python3 "$(dirname "$(readlink -f ~/.claude/commands/ui/context.md)" 2>/dev/null || echo "SCRIPT_DIR")/context_report.py"
```

If the above path fails, try:

```bash
python3 ~/.claude/commands/ui/context_report.py
```

Show the output as-is in a code block. If there are notable findings (approaching compaction, accelerating growth, recommendations), add a brief 1-2 sentence summary after the report.
