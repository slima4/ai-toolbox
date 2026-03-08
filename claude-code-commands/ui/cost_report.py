#!/usr/bin/env python3
"""Cost analysis — spending breakdown, cache savings, projections."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (parse_transcript, get_pricing, calc_cost, format_duration,
                 format_tokens, get_transcript_path)


def main():
    path = get_transcript_path()
    if not path:
        print("Error: No transcript found.")
        sys.exit(1)

    r = parse_transcript(path)
    pricing = get_pricing(r["model"])
    cost = calc_cost(r["tokens"], pricing)
    duration = format_duration(r["start_time"], r["end_time"])

    print(f"""
### Cost Summary

  Model: {r['model']}
  Duration: {duration}
  Turns: {r['turns']}

  Category       │ Tokens          │ Cost       │ $/M
  ───────────────┼─────────────────┼────────────┼──────
  Input          │ {r['tokens']['input']:>15,} │ ${cost['input']:>9.2f} │ ${pricing['input']:.2f}
  Cache Read     │ {r['tokens']['cache_read']:>15,} │ ${cost['cache_read']:>9.2f} │ ${pricing['cache_read']:.2f}
  Output         │ {r['tokens']['output']:>15,} │ ${cost['output']:>9.2f} │ ${pricing['output']:.2f}
  ───────────────┼─────────────────┼────────────┼──────
  Total          │                 │ ${cost['total']:>9.2f} │""")

    # Cache savings
    cache_without = r["tokens"]["cache_read"] * pricing["input"] / 1_000_000
    cache_actual = r["tokens"]["cache_read"] * pricing["cache_read"] / 1_000_000
    saved = cache_without - cache_actual
    save_pct = saved / cache_without * 100 if cache_without > 0 else 0

    print(f"""
### Cache Savings

  Tokens served from cache: {r['tokens']['cache_read']:,}
  Cost with caching:        ${cache_actual:.2f}
  Cost without caching:     ${cache_without:.2f}
  You saved:                ${saved:.2f} ({save_pct:.0f}%)""")

    # Per-turn costs
    per_turn = []
    for resp in r["per_response"]:
        rc = (resp["input"] * pricing["input"] / 1_000_000 +
              resp["cache_read"] * pricing["cache_read"] / 1_000_000 +
              resp["output"] * pricing["output"] / 1_000_000)
        per_turn.append({"turn": resp["turn"], "cost": rc,
                         "output": resp["output"]})

    if per_turn:
        avg = cost["total"] / r["turns"] if r["turns"] > 0 else 0
        most_expensive = max(per_turn, key=lambda x: x["cost"])
        cheapest = min(per_turn, key=lambda x: x["cost"])

        print(f"""
### Cost Per Turn

  Average:          ~${avg:.2f}/turn
  Most expensive:   Turn {most_expensive['turn']} (${most_expensive['cost']:.3f}, {most_expensive['output']:,} output tokens)
  Cheapest:         Turn {cheapest['turn']} (${cheapest['cost']:.4f})""")

    # Cost trend table
    if len(per_turn) >= 2:
        # Aggregate by turn number
        from collections import defaultdict
        turn_costs = defaultdict(float)
        for pt in per_turn:
            turn_costs[pt["turn"]] += pt["cost"]
        sorted_turns = sorted(turn_costs.items())
        last10 = sorted_turns[-10:]

        print(f"""
### Cost Trend (Last 10 Turns)

  Turn │ Cost     │ Cumulative
  ─────┼──────────┼───────────""")
        cumulative = cost["total"] - sum(c for _, c in last10)
        for turn, tc in last10:
            cumulative += tc
            print(f"  {turn:>4} │ ${tc:>7.3f} │ ${cumulative:>8.2f}")

        # Trend direction
        if len(sorted_turns) >= 10:
            first_half = [c for _, c in sorted_turns[:len(sorted_turns)//2]]
            second_half = [c for _, c in sorted_turns[len(sorted_turns)//2:]]
            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)
            if avg_second > avg_first * 1.2:
                trend = "Increasing ↑ — later turns cost more"
            elif avg_second < avg_first * 0.8:
                trend = "Decreasing ↓ — later turns cost less"
            else:
                trend = "Stable → — consistent spend per turn"
            print(f"\n  Trend: {trend}")

    # Projections
    if r["start_time"] and r["end_time"]:
        try:
            from datetime import datetime, timezone
            start = datetime.fromisoformat(r["start_time"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(r["end_time"].replace("Z", "+00:00"))
            mins = max((end - start).total_seconds() / 60, 1)
            cost_per_min = cost["total"] / mins
            cost_per_turn_avg = cost["total"] / max(r["turns"], 1)

            print(f"""
### Budget Projection

  Cost per minute:              ${cost_per_min:.3f}
  Projected for 2h session:     ${cost_per_min * 120:.2f}
  Projected for 10 more turns:  ${cost_per_turn_avg * 10:.2f}""")
        except Exception:
            pass

    print()


if __name__ == "__main__":
    main()
