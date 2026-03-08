#!/usr/bin/env python3
"""Full session report — context, cost, tools, thinking."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (parse_transcript, get_pricing, calc_cost, format_duration,
                 format_tokens, get_transcript_path, CONTEXT_LIMIT)


def main():
    path = get_transcript_path()
    if not path:
        print("Error: No transcript found.")
        sys.exit(1)

    r = parse_transcript(path)
    pricing = get_pricing(r["model"])
    cost = calc_cost(r["tokens"], pricing)
    duration = format_duration(r["start_time"], r["end_time"])
    ratio = r["last_context"] / CONTEXT_LIMIT * 100

    # Compaction prediction
    turns_left = "n/a"
    if r["turns_since_compact"] >= 2 and r["last_context"] > 0:
        growth = r["last_context"] / max(r["turns_since_compact"], 1)
        remaining = CONTEXT_LIMIT - r["last_context"]
        if growth > 0:
            turns_left = str(int(remaining / growth))

    W = 40  # value column width
    rows = [
        ("Context", f"{format_tokens(r['last_context'])} / {format_tokens(CONTEXT_LIMIT)} ({ratio:.1f}%)"),
        ("Turns", str(r['turns'])),
        ("Duration", duration),
        ("Total Cost", f"${cost['total']:.2f}"),
        ("Compactions", str(r['compact_count'])),
        ("Turns to Compact", f"~{turns_left}"),
        ("Model", r['model']),
        ("Session", r['session_id']),
    ]
    label_w = 17
    print(f"\n╔{'═' * (label_w + 2)}╤{'═' * (W + 2)}╗")
    print(f"║ {'SESSION REPORT':^{label_w + W + 3}} ║")
    print(f"╠{'═' * (label_w + 2)}╪{'═' * (W + 2)}╣")
    for label, val in rows:
        print(f"║ {label:<{label_w}} │ {val:<{W}} ║")
    print(f"╚{'═' * (label_w + 2)}╧{'═' * (W + 2)}╝")
    print()

    # Context details
    print("### Context Details\n")
    print("Last 10 responses:")
    print("  Turn │ Context   │ Output")
    print("  ─────┼───────────┼───────────")
    for resp in r["per_response"][-10:]:
        print(f"  {resp['turn']:>4} │ {format_tokens(resp['ctx']):>9} │ {resp['output']:>9,}")

    # Growth analysis
    history = [v for v in r["context_history"] if v is not None]
    if len(history) >= 2:
        last5 = history[-5:] if len(history) >= 5 else history
        growth_last5 = (last5[-1] - last5[0]) / max(len(last5) - 1, 1)
        overall_growth = (history[-1] - history[0]) / max(len(history) - 1, 1)
        print(f"\n  Growth rate (last 5): {format_tokens(int(growth_last5))}/response")
        print(f"  Growth rate (overall): {format_tokens(int(overall_growth))}/response")

    # Top consumers
    top = sorted(r["per_response"], key=lambda x: -x["output"])[:5]
    print("\nTop 5 responses by output tokens:")
    print("  Turn │ Output")
    print("  ─────┼───────────")
    for t in top:
        print(f"  {t['turn']:>4} │ {t['output']:>9,}")

    # Cost breakdown
    cache_without = r["tokens"]["cache_read"] * pricing["input"] / 1_000_000
    cache_actual = r["tokens"]["cache_read"] * pricing["cache_read"] / 1_000_000
    saved = cache_without - cache_actual
    avg_cost = cost["total"] / r["turns"] if r["turns"] > 0 else 0

    print(f"""
### Cost Breakdown

  Category       │ Tokens          │ Cost
  ───────────────┼─────────────────┼──────────
  Input          │ {r['tokens']['input']:>15,} │ ${cost['input']:.2f}
  Cache Read     │ {r['tokens']['cache_read']:>15,} │ ${cost['cache_read']:.2f}
  Output         │ {r['tokens']['output']:>15,} │ ${cost['output']:.2f}
  ───────────────┼─────────────────┼──────────
  Total          │                 │ ${cost['total']:.2f}

  Cache savings: ${saved:.2f}
  Avg cost/turn: ~${avg_cost:.2f}""")

    # Cost trend
    per_resp_costs = []
    for resp in r["per_response"]:
        rc = resp["output"] * pricing["output"] / 1_000_000
        per_resp_costs.append(rc)
    if len(per_resp_costs) >= 10:
        first5 = sum(per_resp_costs[:5]) / 5
        last5 = sum(per_resp_costs[-5:]) / 5
        if last5 > first5 * 1.2:
            trend = "increasing ↑"
        elif last5 < first5 * 0.8:
            trend = "decreasing ↓"
        else:
            trend = "stable →"
        print(f"  Cost trend: {trend}")

    # Tool activity
    print(f"""
### Tool Activity

  Tool           │ Calls
  ───────────────┼──────""")
    for tool, count in r["tool_counts"].most_common(15):
        print(f"  {tool:<14} │ {count}")
    total_tools = sum(r["tool_counts"].values())
    print(f"  ───────────────┼──────")
    print(f"  Total          │ {total_tools}")
    if r["tool_errors"] > 0:
        print(f"\n  Errors: {r['tool_errors']}")
        for err in r["tool_error_details"][-5:]:
            print(f"    Turn {err['turn']}: {err['error']}")

    # Files
    print("\nMost active files:")
    print("  File                          │ Reads │ Edits")
    print("  ──────────────────────────────┼───────┼──────")
    all_files = set(list(r["files_read"].keys()) + list(r["files_edited"].keys()))
    file_activity = []
    for f in all_files:
        file_activity.append((f, r["files_read"].get(f, 0), r["files_edited"].get(f, 0)))
    file_activity.sort(key=lambda x: -(x[1] + x[2]))
    for fname, reads, edits in file_activity[:10]:
        print(f"  {fname:<30} │ {reads:>5} │ {edits:>5}")

    # Compaction history
    if r["compact_events"]:
        print(f"""
### Compaction History

  # │ Turn │ Context Before  │ Turns Between
  ──┼──────┼─────────────────┼──────────────""")
        for i, evt in enumerate(r["compact_events"], 1):
            print(f"  {i} │ {evt['turn']:>4} │ {format_tokens(evt['context_before']):>15} │ {evt['turns_since_last']:>13}")

    # Thinking
    think_pct = r["thinking_count"] / max(r["responses"], 1) * 100
    print(f"""
### Thinking Analysis

  Extended thinking: {r['thinking_count']}/{r['responses']} responses ({think_pct:.1f}%)""")

    if r["subagent_count"] > 0:
        print(f"  Sub-agents spawned: {r['subagent_count']}")

    print()


if __name__ == "__main__":
    main()
