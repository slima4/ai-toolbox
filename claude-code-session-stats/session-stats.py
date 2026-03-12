#!/usr/bin/env python3
"""
Claude Code Session Stats — Post-Session Analytics

Analyzes Claude Code transcript files to generate detailed session reports
including cost breakdown, token usage over time, file activity, compaction
timeline, and tool usage statistics.

Usage:
    # Analyze the most recent session
    python3 session-stats.py

    # Analyze a specific session by ID
    python3 session-stats.py abc12345

    # Analyze a specific project
    python3 session-stats.py --project my-project

    # Analyze all sessions from the last 7 days
    python3 session-stats.py --days 7

    # Export as JSON
    python3 session-stats.py --json
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Pricing per million tokens
MODEL_PRICING = {
    "claude-opus-4-6": {"input": 15.0, "cache_read": 1.5, "output": 75.0},
    "claude-sonnet-4-6": {"input": 3.0, "cache_read": 0.30, "output": 15.0},
    "claude-haiku-4-5": {"input": 0.80, "cache_read": 0.08, "output": 4.0},
    "claude-sonnet-3-5": {"input": 3.0, "cache_read": 0.30, "output": 15.0},
    "claude-haiku-3-5": {"input": 0.80, "cache_read": 0.08, "output": 4.0},
}

# ANSI
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
ORANGE = "\033[38;5;208m"
RED = "\033[91m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
GRAY = "\033[90m"
DIM = "\033[2m"


def get_projects_dir():
    """Get the Claude Code projects directory."""
    return Path.home() / ".claude" / "projects"


def find_sessions(project_filter=None, days=None, session_id=None):
    """Find transcript files matching the given filters."""
    projects_dir = get_projects_dir()
    if not projects_dir.exists():
        return []

    sessions = []
    cutoff = None
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        project_name = project_dir.name

        if project_filter and project_filter.lower() not in project_name.lower():
            continue

        for jsonl_file in project_dir.glob("*.jsonl"):
            sid = jsonl_file.stem

            if session_id and not sid.startswith(session_id):
                continue

            mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime, tz=timezone.utc)
            if cutoff and mtime < cutoff:
                continue

            sessions.append({
                "path": jsonl_file,
                "session_id": sid,
                "project": project_name,
                "modified": mtime,
                "size": jsonl_file.stat().st_size,
            })

    sessions.sort(key=lambda s: s["modified"], reverse=True)
    return sessions


def parse_session(transcript_path):
    """Parse a transcript file into a full analytics report."""
    report = {
        "session_id": Path(transcript_path).stem,
        "project": Path(transcript_path).parent.name,
        "start_time": None,
        "end_time": None,
        "duration_minutes": 0,
        "model": "",
        "version": "",
        "git_branch": "",
        "tokens": {
            "input_total": 0,
            "cache_read_total": 0,
            "cache_creation_total": 0,
            "output_total": 0,
        },
        "cost": {
            "input": 0.0,
            "cache_read": 0.0,
            "output": 0.0,
            "total": 0.0,
        },
        "compactions": [],
        "compact_count": 0,
        "turns": 0,
        "user_messages": 0,
        "assistant_messages": 0,
        "tool_usage": Counter(),
        "tool_errors": 0,
        "files_read": Counter(),
        "files_edited": Counter(),
        "files_created": Counter(),
        "subagent_count": 0,
        "skill_usage": Counter(),
        "context_over_time": [],
    }

    try:
        with open(transcript_path, "r") as f:
            lines = f.readlines()
    except (FileNotFoundError, PermissionError):
        return report

    subagents = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        timestamp = obj.get("timestamp")
        entry_type = obj.get("type", "")

        # Track time range
        if timestamp:
            if report["start_time"] is None:
                report["start_time"] = timestamp
            report["end_time"] = timestamp

        # Model and version from first assistant message
        if not report["model"] and entry_type == "assistant" and "message" in obj:
            report["model"] = obj["message"].get("model", "")
        if not report["version"] and "version" in obj:
            report["version"] = obj["version"]
        if not report["git_branch"] and "gitBranch" in obj:
            report["git_branch"] = obj["gitBranch"]

        # User messages (non-meta)
        if entry_type == "user" and not obj.get("isMeta"):
            report["user_messages"] += 1
            report["turns"] += 1

        # Assistant messages with usage
        if entry_type == "assistant" and "message" in obj:
            msg = obj["message"]

            if "usage" in msg:
                report["assistant_messages"] += 1
                usage = msg["usage"]
                input_t = usage.get("input_tokens", 0)
                cache_read_t = usage.get("cache_read_input_tokens", 0)
                cache_create_t = usage.get("cache_creation_input_tokens", 0)
                output_t = usage.get("output_tokens", 0)

                report["tokens"]["input_total"] += input_t
                report["tokens"]["cache_read_total"] += cache_read_t
                report["tokens"]["cache_creation_total"] += cache_create_t
                report["tokens"]["output_total"] += output_t

                context_size = input_t + cache_read_t + cache_create_t + output_t
                if timestamp:
                    report["context_over_time"].append({
                        "time": timestamp,
                        "tokens": context_size,
                    })

            # Tool usage and file tracking
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use":
                        continue

                    tool_name = block.get("name", "unknown")
                    report["tool_usage"][tool_name] += 1
                    inp = block.get("input", {})

                    if tool_name in ("Task", "Agent"):
                        tid = block.get("id", "")
                        if tid:
                            subagents.add(tid)

                    if tool_name == "Skill":
                        skill_name = inp.get("skill", "")
                        if skill_name:
                            report["skill_usage"]["/" + skill_name] += 1

                    file_path = inp.get("file_path", inp.get("path", ""))
                    if not file_path:
                        continue

                    if tool_name == "Read":
                        report["files_read"][file_path] += 1
                    elif tool_name == "Edit":
                        report["files_edited"][file_path] += 1
                    elif tool_name == "Write":
                        report["files_created"][file_path] += 1

        # Compaction events
        if (entry_type == "summary" or
                (entry_type == "system" and obj.get("subtype") == "compact_boundary")):
            report["compact_count"] += 1
            if timestamp:
                report["compactions"].append(timestamp)

        # Tool errors
        if entry_type == "user" and "message" in obj:
            content = obj["message"].get("content", [])
            if isinstance(content, list):
                for block in content:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "tool_result"
                        and block.get("is_error")
                    ):
                        report["tool_errors"] += 1

    report["subagent_count"] = len(subagents)

    # Calculate duration
    if report["start_time"] and report["end_time"]:
        try:
            start = datetime.fromisoformat(
                report["start_time"].replace("Z", "+00:00")
            )
            end = datetime.fromisoformat(
                report["end_time"].replace("Z", "+00:00")
            )
            report["duration_minutes"] = int((end - start).total_seconds() / 60)
        except Exception:
            pass

    # Calculate cost
    pricing = MODEL_PRICING.get("claude-sonnet-4-6")
    for key, p in MODEL_PRICING.items():
        if key in report["model"]:
            pricing = p
            break

    report["cost"]["input"] = (
        report["tokens"]["input_total"] * pricing["input"] / 1_000_000
    )
    report["cost"]["cache_read"] = (
        report["tokens"]["cache_read_total"] * pricing["cache_read"] / 1_000_000
    )
    report["cost"]["output"] = (
        report["tokens"]["output_total"] * pricing["output"] / 1_000_000
    )
    report["cost"]["total"] = sum([
        report["cost"]["input"],
        report["cost"]["cache_read"],
        report["cost"]["output"],
    ])

    return report


def format_duration(minutes):
    """Format minutes into human-readable duration."""
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins:02d}m"


def format_tokens(n):
    """Format token count."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def format_timestamp(ts):
    """Format ISO timestamp to local time."""
    if not ts:
        return "?"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts[:16]


def render_sparkline(data_points, width=40):
    """Render a simple sparkline chart of context usage over time."""
    if not data_points:
        return ""

    values = [p["tokens"] for p in data_points]
    max_val = max(values) if values else 1
    blocks = " ▁▂▃▄▅▆▇█"

    # Downsample to fit width
    if len(values) > width:
        step = len(values) / width
        sampled = []
        for i in range(width):
            idx = int(i * step)
            sampled.append(values[idx])
        values = sampled

    line = ""
    for v in values:
        idx = int(v / max_val * (len(blocks) - 1)) if max_val > 0 else 0
        line += blocks[idx]

    return line


def print_report(report):
    """Print a formatted session report to the terminal."""
    print()
    print(f"  {BOLD}{WHITE}Session Report{RESET}")
    print(f"  {GRAY}{'─' * 60}{RESET}")

    # Header
    project_short = report["project"].split("-")[-1] if report["project"] else "?"
    print(f"  {GRAY}Session:  {RESET}{report['session_id'][:8]}")
    print(f"  {GRAY}Project:  {RESET}{project_short}")
    print(f"  {GRAY}Model:    {RESET}{report['model']}")
    if report["git_branch"]:
        print(f"  {GRAY}Branch:   {RESET}{GREEN}{report['git_branch']}{RESET}")
    print(f"  {GRAY}Started:  {RESET}{format_timestamp(report['start_time'])}")
    print(f"  {GRAY}Duration: {RESET}{format_duration(report['duration_minutes'])}")
    print(f"  {GRAY}Version:  {RESET}{report['version']}")

    # Cost breakdown
    print()
    print(f"  {BOLD}{YELLOW}Cost Breakdown{RESET}")
    print(f"  {GRAY}{'─' * 40}{RESET}")
    print(f"  Input tokens:      {format_tokens(report['tokens']['input_total']):>10}  {GRAY}${report['cost']['input']:.2f}{RESET}")
    print(f"  Cache read tokens: {format_tokens(report['tokens']['cache_read_total']):>10}  {GRAY}${report['cost']['cache_read']:.2f}{RESET}")
    print(f"  Output tokens:     {format_tokens(report['tokens']['output_total']):>10}  {GRAY}${report['cost']['output']:.2f}{RESET}")
    print(f"  {GRAY}{'─' * 40}{RESET}")
    cost_color = GREEN if report["cost"]["total"] < 1 else YELLOW if report["cost"]["total"] < 5 else RED
    print(f"  {BOLD}Total:               {' ' * 10}  {cost_color}${report['cost']['total']:.2f}{RESET}")

    # Context over time
    if report["context_over_time"]:
        print()
        print(f"  {BOLD}{CYAN}Context Usage Over Time{RESET}")
        print(f"  {GRAY}{'─' * 40}{RESET}")
        sparkline = render_sparkline(report["context_over_time"])
        print(f"  {CYAN}{sparkline}{RESET}")
        peak = max(p["tokens"] for p in report["context_over_time"])
        print(f"  {GRAY}peak: {format_tokens(peak)}{RESET}")

    # Activity
    print()
    print(f"  {BOLD}{WHITE}Activity{RESET}")
    print(f"  {GRAY}{'─' * 40}{RESET}")
    print(f"  User messages:   {report['user_messages']}")
    print(f"  Turns:           {report['turns']}")
    print(f"  Compactions:     {report['compact_count']}")
    if report["compactions"]:
        for i, ts in enumerate(report["compactions"], 1):
            print(f"    {GRAY}#{i} at {format_timestamp(ts)}{RESET}")
    print(f"  Sub-agents:      {report['subagent_count']}")
    print(f"  Tool errors:     {RED if report['tool_errors'] > 0 else GREEN}{report['tool_errors']}{RESET}")

    # Tool usage
    if report["tool_usage"]:
        print()
        print(f"  {BOLD}{MAGENTA}Tool Usage{RESET}")
        print(f"  {GRAY}{'─' * 40}{RESET}")
        for tool, count in report["tool_usage"].most_common(10):
            bar_len = min(count, 30)
            bar = "█" * bar_len
            print(f"  {tool:15} {count:4}  {MAGENTA}{bar}{RESET}")

    # Skill usage
    if report["skill_usage"]:
        print()
        print(f"  {BOLD}{CYAN}Skills & Commands{RESET}")
        print(f"  {GRAY}{'─' * 40}{RESET}")
        for skill, count in report["skill_usage"].most_common(10):
            bar_len = min(count, 30)
            bar = "█" * bar_len
            print(f"  {skill:25} {count:4}  {CYAN}{bar}{RESET}")

    # Most active files
    all_files = Counter()
    all_files.update(report["files_read"])
    all_files.update(report["files_edited"])
    all_files.update(report["files_created"])

    if all_files:
        print()
        print(f"  {BOLD}{WHITE}Most Active Files{RESET}")
        print(f"  {GRAY}{'─' * 40}{RESET}")
        for filepath, count in all_files.most_common(10):
            # Shorten path
            short = filepath
            home = str(Path.home())
            if short.startswith(home):
                short = "~" + short[len(home):]
            if len(short) > 50:
                short = "..." + short[-47:]

            read_c = report["files_read"].get(filepath, 0)
            edit_c = report["files_edited"].get(filepath, 0)
            create_c = report["files_created"].get(filepath, 0)

            tags = []
            if read_c:
                tags.append(f"{GRAY}r:{read_c}{RESET}")
            if edit_c:
                tags.append(f"{YELLOW}e:{edit_c}{RESET}")
            if create_c:
                tags.append(f"{GREEN}w:{create_c}{RESET}")

            print(f"  {short:50} {' '.join(tags)}")

    # Avg turns between compactions
    if report["compact_count"] > 0:
        avg_turns = report["turns"] // (report["compact_count"] + 1)
        print()
        print(f"  {GRAY}Avg turns between compactions: ~{avg_turns}{RESET}")

    print()


def print_summary_table(sessions_reports):
    """Print a summary table of multiple sessions."""
    print()
    print(f"  {BOLD}{WHITE}Session Summary ({len(sessions_reports)} sessions){RESET}")
    print(f"  {GRAY}{'─' * 90}{RESET}")
    print(f"  {GRAY}{'ID':8} {'Date':12} {'Duration':>8} {'Cost':>8} {'Turns':>6} {'Compact':>8} {'Model':20}{RESET}")
    print(f"  {GRAY}{'─' * 90}{RESET}")

    total_cost = 0
    total_duration = 0

    for r in sessions_reports:
        sid = r["session_id"][:8]
        date = format_timestamp(r["start_time"])[:10] if r["start_time"] else "?"
        duration = format_duration(r["duration_minutes"])
        cost = r["cost"]["total"]
        total_cost += cost
        total_duration += r["duration_minutes"]
        cost_color = GREEN if cost < 1 else YELLOW if cost < 5 else RED
        model_short = r["model"].replace("claude-", "").replace("-", " ") if r["model"] else "?"

        print(
            f"  {WHITE}{sid}{RESET} {date:12} {duration:>8} "
            f"{cost_color}${cost:>6.2f}{RESET} {r['turns']:>6} "
            f"{r['compact_count']:>8} {GRAY}{model_short:20}{RESET}"
        )

    print(f"  {GRAY}{'─' * 90}{RESET}")
    total_cost_color = GREEN if total_cost < 5 else YELLOW if total_cost < 20 else RED
    print(
        f"  {'Total':8} {'':12} {format_duration(total_duration):>8} "
        f"{total_cost_color}${total_cost:>6.2f}{RESET}"
    )

    # Aggregate skill usage across all sessions
    all_skills = Counter()
    for r in sessions_reports:
        all_skills.update(r.get("skill_usage", {}))
    if all_skills:
        print()
        print(f"  {BOLD}{CYAN}Skills & Commands (across sessions){RESET}")
        print(f"  {GRAY}{'─' * 50}{RESET}")
        for skill, count in all_skills.most_common(10):
            bar_len = min(count, 30)
            bar = "█" * bar_len
            sessions_with = sum(1 for r in sessions_reports if skill in r.get("skill_usage", {}))
            print(f"  {skill:25} {count:4}  {GRAY}({sessions_with} sessions){RESET}  {CYAN}{bar}{RESET}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Claude Code Session Analytics"
    )
    parser.add_argument(
        "session_id", nargs="?",
        help="Session ID (prefix match) to analyze"
    )
    parser.add_argument(
        "--project", "-p",
        help="Filter by project name (substring match)"
    )
    parser.add_argument(
        "--days", "-d", type=int,
        help="Show sessions from the last N days"
    )
    parser.add_argument(
        "--json", "-j", action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--summary", "-s", action="store_true",
        help="Show summary table of all matching sessions"
    )
    args = parser.parse_args()

    sessions = find_sessions(
        project_filter=args.project,
        days=args.days,
        session_id=args.session_id,
    )

    if not sessions:
        print(f"  {RED}No sessions found.{RESET}")
        print(f"  {GRAY}Looked in: {get_projects_dir()}{RESET}")
        sys.exit(1)

    if args.summary or (not args.session_id and args.days):
        reports = [parse_session(s["path"]) for s in sessions]
        if args.json:
            # Convert Counters to dicts for JSON serialization
            for r in reports:
                r["tool_usage"] = dict(r["tool_usage"])
                r["files_read"] = dict(r["files_read"])
                r["files_edited"] = dict(r["files_edited"])
                r["files_created"] = dict(r["files_created"])
            print(json.dumps(reports, indent=2))
        else:
            print_summary_table(reports)
        return

    # Single session (most recent or matched)
    session = sessions[0]
    report = parse_session(session["path"])

    if args.json:
        report["tool_usage"] = dict(report["tool_usage"])
        report["files_read"] = dict(report["files_read"])
        report["files_edited"] = dict(report["files_edited"])
        report["files_created"] = dict(report["files_created"])
        print(json.dumps(report, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
