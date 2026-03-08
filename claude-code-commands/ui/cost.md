---
description: Detailed cost analysis — spending breakdown, cache savings, cost trends, budget projection
allowed-tools: Bash
---

Run the cost report script and present the output to the user. Do not add commentary — just show the report.

```bash
python3 "$(dirname "$(readlink -f ~/.claude/commands/ui/cost.md)" 2>/dev/null || echo "SCRIPT_DIR")/cost_report.py"
```

If the above path fails, try:

```bash
python3 ~/.claude/commands/ui/cost_report.py
```

Show the output as-is in a code block. If there are notable findings (high cache savings, cost trend changes, budget concerns), add a brief 1-2 sentence summary after the report.
