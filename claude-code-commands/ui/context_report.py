#!/usr/bin/env python3
"""Context window analysis — growth curve, compaction timeline, predictions."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (parse_transcript, format_duration, format_tokens,
                 get_transcript_path, CONTEXT_LIMIT)


def draw_chart(history, width=50, height=10):
    """Draw an ASCII chart of context usage over time."""
    # Filter out None (compaction markers) for charting, mark positions
    points = []
    compact_indices = set()
    for i, v in enumerate(history):
        if v is None:
            compact_indices.add(len(points))
            points.append(0)
        else:
            points.append(v)

    if not points:
        return ""

    # Downsample to width
    if len(points) > width:
        step = len(points) / width
        sampled = []
        compact_sampled = set()
        for i in range(width):
            start = int(i * step)
            end = int((i + 1) * step)
            chunk = points[start:end]
            sampled.append(max(chunk))
            for j in range(start, end):
                if j in compact_indices:
                    compact_sampled.add(i)
        points = sampled
        compact_indices = compact_sampled

    scale = CONTEXT_LIMIT
    lines = []
    for row in range(height, -1, -1):
        threshold = row / height * scale
        if row == height:
            label = f"{format_tokens(int(scale)):>5} ┤"
        elif row == height // 2:
            label = f"{format_tokens(int(scale // 2)):>5} ┤"
        elif row == 0:
            label = "    0 ┼"
        else:
            label = "      │"
        chars = []
        for i, v in enumerate(points):
            if i in compact_indices and row == 0:
                chars.append("↓")
            elif v >= threshold:
                chars.append("█")
            else:
                chars.append(" ")
        lines.append(label + "".join(chars))

    # X axis
    axis = "      └" + "─" * len(points)
    lines.append(axis)
    return "\n".join(lines)


def main():
    path = get_transcript_path()
    if not path:
        print("Error: No transcript found.")
        sys.exit(1)

    r = parse_transcript(path)
    duration = format_duration(r["start_time"], r["end_time"])
    ratio = r["last_context"] / CONTEXT_LIMIT * 100
    remaining = CONTEXT_LIMIT - r["last_context"]

    # Growth rates
    history = [v for v in r["context_history"] if v is not None]
    overall_growth = 0
    last5_growth = 0
    last10_growth = 0
    if len(history) >= 2:
        overall_growth = (history[-1] - history[0]) / (len(history) - 1)
    if len(history) >= 6:
        h5 = history[-5:]
        last5_growth = (h5[-1] - h5[0]) / (len(h5) - 1)
    if len(history) >= 11:
        h10 = history[-10:]
        last10_growth = (h10[-1] - h10[0]) / (len(h10) - 1)

    def predict_turns(growth):
        if growth > 0:
            return str(int(remaining / growth))
        return "∞"

    print(f"""
### Current State

  Metric              │ Value
  ────────────────────┼──────────────────────────
  Context used        │ {format_tokens(r['last_context'])} / {format_tokens(CONTEXT_LIMIT)} ({ratio:.1f}%)
  Remaining capacity  │ {format_tokens(remaining)} ({100 - ratio:.1f}%)
  Turns in session    │ {r['turns']}
  Compactions         │ {r['compact_count']}
  Duration            │ {duration}
  Turns since compact │ {r['turns_since_compact']}
""")

    # Growth chart
    print("### Context Growth Curve\n")
    chart = draw_chart(r["context_history"])
    if chart:
        print(chart)
    print()

    # Compaction timeline
    if r["compact_events"]:
        print("### Compaction Timeline\n")
        print("  #  │ Turn │ Context Before │ Turns Between")
        print("  ───┼──────┼───────────────┼──────────────")
        for i, evt in enumerate(r["compact_events"], 1):
            print(f"  {i:>2} │ {evt['turn']:>4} │ {format_tokens(evt['context_before']):>13} │ {evt['turns_since_last']:>13}")
        avg_turns_between = sum(
            e["turns_since_last"] for e in r["compact_events"]
        ) / len(r["compact_events"])
        print(f"\n  Average turns between compactions: {avg_turns_between:.0f}")

    # Growth analysis
    print(f"""
### Growth Analysis

  Period         │ Growth/Response │ Turns to Compact
  ───────────────┼─────────────────┼─────────────────
  Last 5         │ {format_tokens(int(last5_growth)):>15} │ ~{predict_turns(last5_growth):>14}
  Last 10        │ {format_tokens(int(last10_growth)):>15} │ ~{predict_turns(last10_growth):>14}
  Overall        │ {format_tokens(int(overall_growth)):>15} │ ~{predict_turns(overall_growth):>14}""")

    # Per-turn breakdown
    print(f"""
### Per-Turn Breakdown (Last 15 Responses)

  Turn │ Context   │ Delta     │ % Used │ Note
  ─────┼───────────┼───────────┼────────┼──────────""")
    responses = r["per_response"]
    prev_ctx = responses[-16]["ctx"] if len(responses) >= 16 else 0
    avg_delta = overall_growth if overall_growth > 0 else 1

    for resp in responses[-15:]:
        delta = resp["ctx"] - prev_ctx
        pct = resp["ctx"] / CONTEXT_LIMIT * 100
        note = ""
        if delta > avg_delta * 3 and avg_delta > 0:
            note = "large growth"
        if delta < 0:
            note = "after compact"
        print(f"  {resp['turn']:>4} │ {format_tokens(resp['ctx']):>9} │ {'+' if delta >= 0 else ''}{format_tokens(int(delta)):>8} │ {pct:>5.1f}% │ {note}")
        prev_ctx = resp["ctx"]

    # Recommendations
    print("\n### Recommendations\n")
    if ratio > 80:
        print("  ⚠ Context usage is high. Consider compacting soon with /compact.")
    elif ratio > 60:
        print("  ℹ Context at moderate usage. Monitor growth rate.")
    else:
        print("  ✓ Context usage is healthy. Plenty of room remaining.")

    if r["compact_count"] >= 3:
        print("  ⚠ Multiple compactions detected. Consider starting a fresh session.")

    if last5_growth > overall_growth * 2 and overall_growth > 0:
        print("  ⚠ Growth rate accelerating. Recent turns consuming more context.")

    print()


if __name__ == "__main__":
    main()
