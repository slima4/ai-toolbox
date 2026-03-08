---
description: Performance analysis — tool efficiency, error patterns, file activity heatmap, thinking usage
allowed-tools: Bash
---

Run the performance report script and present the output to the user. Do not add commentary — just show the report.

```bash
python3 "$(dirname "$(readlink -f ~/.claude/commands/ui/perf.md)" 2>/dev/null || echo "SCRIPT_DIR")/perf_report.py"
```

If the above path fails, try:

```bash
python3 ~/.claude/commands/ui/perf_report.py
```

Show the output as-is in a code block. If there are notable findings (high error rates, unusual tool patterns, efficiency concerns), add a brief 1-2 sentence summary after the report.
