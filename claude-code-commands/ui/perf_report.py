#!/usr/bin/env python3
"""Performance analysis — tool efficiency, errors, file heatmap."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (parse_transcript, get_pricing, format_duration,
                 get_transcript_path)


def main():
    path = get_transcript_path()
    if not path:
        print("Error: No transcript found.")
        sys.exit(1)

    r = parse_transcript(path)
    duration = format_duration(r["start_time"], r["end_time"])
    total_tools = sum(r["tool_counts"].values())
    tools_per_turn = total_tools / max(r["turns"], 1)
    success_rate = ((total_tools - r["tool_errors"]) / max(total_tools, 1)
                    * 100)

    print(f"""
### Performance Summary

  Duration: {duration}
  Turns: {r['turns']}
  Total tool calls: {total_tools}
  Tools per turn: {tools_per_turn:.1f}
  Overall success rate: {success_rate:.1f}%
""")

    # Tool usage
    print("### Tool Usage\n")
    print("  Tool           │ Calls │ Success Rate")
    print("  ───────────────┼───────┼─────────────")
    for tool, count in r["tool_counts"].most_common(15):
        # We don't have per-tool errors, so show overall
        print(f"  {tool:<14} │ {count:>5} │ —")
    print(f"  ───────────────┼───────┼─────────────")
    print(f"  Total          │ {total_tools:>5} │ {success_rate:.1f}%")

    # Error analysis
    if r["tool_errors"] > 0:
        print(f"\n### Error Analysis\n")
        print(f"  Total errors: {r['tool_errors']}")
        if r["tool_error_details"]:
            print(f"\n  Recent errors:")
            for err in r["tool_error_details"][-10:]:
                print(f"    Turn {err['turn']}: {err['error']}")

    # File heatmap
    print("\n### File Activity Heatmap\n")
    print("  File                          │ Reads │ Edits │ Total")
    print("  ──────────────────────────────┼───────┼───────┼──────")
    all_files = set(list(r["files_read"].keys()) +
                    list(r["files_edited"].keys()))
    file_activity = []
    for f in all_files:
        reads = r["files_read"].get(f, 0)
        edits = r["files_edited"].get(f, 0)
        file_activity.append((f, reads, edits, reads + edits))
    file_activity.sort(key=lambda x: -x[3])
    for fname, reads, edits, total in file_activity[:15]:
        bar = "█" * min(total, 30)
        print(f"  {fname:<30} │ {reads:>5} │ {edits:>5} │ {total:>5} {bar}")

    # Efficiency metrics
    read_count = r["tool_counts"].get("Read", 0)
    edit_count = (r["tool_counts"].get("Edit", 0) +
                  r["tool_counts"].get("Write", 0) +
                  r["tool_counts"].get("MultiEdit", 0))
    read_edit_ratio = read_count / max(edit_count, 1)
    turns_with_errors = len(set(e["turn"] for e in r["tool_error_details"]))

    print(f"""
### Efficiency Metrics

  Tools per turn:       {tools_per_turn:.1f}
  Read/Edit ratio:      {read_edit_ratio:.1f}:1
  Turns with errors:    {turns_with_errors}/{r['turns']} ({turns_with_errors / max(r['turns'], 1) * 100:.1f}%)
  Unique files touched: {len(all_files)}""")

    # Thinking analysis
    think_pct = r["thinking_count"] / max(r["responses"], 1) * 100
    print(f"""
### Thinking Analysis

  Responses with thinking: {r['thinking_count']}/{r['responses']} ({think_pct:.1f}%)""")

    # Sub-agents
    if r["subagent_count"] > 0:
        print(f"  Sub-agents spawned: {r['subagent_count']}")

    # Session flow analysis
    if r["per_response"]:
        print("\n### Session Flow\n")
        # Divide session into phases based on tool patterns
        chunk_size = max(r["turns"] // 4, 1)
        phases = []
        turn_tools = {}
        for tool, _ in r["tool_counts"].items():
            pass
        # Simplified: just show read vs edit ratio over time
        responses = r["per_response"]
        n = len(responses)
        if n >= 4:
            quarter = n // 4
            for i, label in enumerate(["Early", "Mid-early", "Mid-late", "Late"]):
                chunk = responses[i * quarter:(i + 1) * quarter]
                out_total = sum(c["output"] for c in chunk)
                print(f"  {label:<10} │ {len(chunk)} responses │ {out_total:,} output tokens")

    print()


if __name__ == "__main__":
    main()
