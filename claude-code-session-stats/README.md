# Claude Code Session Stats — Post-Session Analytics

Analyzes Claude Code transcript files and generates detailed session reports with cost breakdown, token usage sparkline, file activity, compaction timeline, and tool usage statistics.

## Usage

```bash
# Analyze the most recent session
python3 session-stats.py

# Analyze a specific session by ID prefix
python3 session-stats.py abc12345

# Analyze sessions for a specific project
python3 session-stats.py --project my-project

# Summary table of all sessions from the last 7 days
python3 session-stats.py --days 7 --summary

# Export as JSON
python3 session-stats.py abc12345 --json
```

## What it shows

### Single session report

- **Cost breakdown** — input, cache read, and output token costs by model pricing
- **Context usage sparkline** — visual chart of context window size over time
- **Activity** — user messages, turns, compaction count with timestamps, sub-agents spawned, tool errors
- **Tool usage** — ranked bar chart of which tools were called and how often
- **Skills & commands** — which skills and slash commands were used, ranked by frequency
- **Most active files** — files ranked by read/edit/write activity with per-operation counts
- **Avg turns between compactions** — helps gauge session efficiency

### Multi-session summary (`--summary`)

```bash
python3 session-stats.py --days 7 --summary
```

```
  Session Summary (6 sessions)
  ──────────────────────────────────────────────────────────────────────────────────────────
  ID       Date         Duration     Cost  Turns  Compact Model
  ──────────────────────────────────────────────────────────────────────────────────────────
  a1b2c3d4 2026-03-08        45m $  2.31     34        0 opus 4 6
  e5f6a7b8 2026-03-07     2h 10m $ 12.47    156        1 sonnet 4 6
  c9d0e1f2 2026-03-04        18m $  0.52     12        0 opus 4 6
  13a4b5c6 2026-03-03     5h 22m $ 45.80    287        2 opus 4 6
  d7e8f9a0 2026-03-02     1h 05m $  8.14     89        0 sonnet 4 6
  b1c2d3e4 2026-03-01     3h 40m $ 28.55    198        1 opus 4 6
  ──────────────────────────────────────────────────────────────────────────────────────────
  Total                  13h 20m $ 97.79
```

## Requirements

- Python 3.8+
- No external dependencies

## Supported models

| Model | Input | Cache Read | Output |
| ----- | ----- | ---------- | ------ |
| Claude Opus 4.6 | $15/M | $1.50/M | $75/M |
| Claude Sonnet 4.6 | $3/M | $0.30/M | $15/M |
| Claude Haiku 4.5 | $0.80/M | $0.08/M | $4/M |

## License

MIT
