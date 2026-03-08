"""Shared parsing and formatting for UI commands."""

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

MODEL_PRICING = {
    "claude-opus-4-6": {"input": 15.0, "cache_read": 1.5, "output": 75.0},
    "claude-sonnet-4-6": {"input": 3.0, "cache_read": 0.30, "output": 15.0},
    "claude-haiku-4-5": {"input": 0.80, "cache_read": 0.08, "output": 4.0},
}
CONTEXT_LIMIT = 200_000


def find_transcript(cwd=None):
    """Find the most recent transcript for the given working directory."""
    if cwd is None:
        cwd = os.getcwd()
    projects_dir = Path.home() / ".claude" / "projects"
    # Claude Code uses the absolute path with / replaced by - and leading -
    project_name = "-" + cwd.replace("/", "-").lstrip("-")
    project_dir = projects_dir / project_name
    if not project_dir.exists():
        # Try without leading dash
        project_name = cwd.replace("/", "-").lstrip("-")
        project_dir = projects_dir / project_name
    if not project_dir.exists():
        return None
    jsonl_files = sorted(project_dir.glob("*.jsonl"),
                         key=lambda f: f.stat().st_mtime, reverse=True)
    return str(jsonl_files[0]) if jsonl_files else None


def parse_transcript(path):
    """Parse a transcript JSONL file into a comprehensive report dict."""
    r = {
        "path": path,
        "model": "",
        "session_id": Path(path).stem[:8],
        "start_time": None,
        "end_time": None,
        "turns": 0,
        "responses": 0,
        "compact_count": 0,
        "compact_events": [],
        "tokens": {
            "input": 0, "cache_read": 0,
            "cache_creation": 0, "output": 0,
        },
        "context_history": [],
        "per_response": [],
        "tool_counts": Counter(),
        "tool_errors": 0,
        "tool_error_details": [],
        "files_read": Counter(),
        "files_edited": Counter(),
        "thinking_count": 0,
        "subagent_count": 0,
        "turns_since_compact": 0,
    }

    try:
        with open(path, "r") as f:
            lines = f.readlines()
    except (FileNotFoundError, PermissionError):
        return r

    subagents = set()
    current_turn = 0
    last_context = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        ts = obj.get("timestamp")
        etype = obj.get("type", "")

        if ts:
            if r["start_time"] is None:
                r["start_time"] = ts
            r["end_time"] = ts

        if not r["model"] and etype == "assistant" and "message" in obj:
            r["model"] = obj["message"].get("model", "")

        # User turns
        if etype == "user" and not obj.get("isMeta"):
            content = obj.get("message", {}).get("content", "")
            has_text = False
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        has_text = True
                        break
            elif isinstance(content, str) and content.strip():
                has_text = True
            if has_text:
                current_turn += 1
                r["turns"] += 1
                r["turns_since_compact"] += 1

        # Tool errors
        if etype == "user" and "message" in obj:
            content = obj.get("message", {}).get("content", [])
            if isinstance(content, list):
                for block in content:
                    if (isinstance(block, dict)
                            and block.get("type") == "tool_result"
                            and block.get("is_error")):
                        r["tool_errors"] += 1
                        tool_id = block.get("tool_use_id", "")
                        error_text = ""
                        bc = block.get("content", "")
                        if isinstance(bc, list):
                            for b in bc:
                                if isinstance(b, dict) and b.get("type") == "text":
                                    error_text = b.get("text", "")[:100]
                                    break
                        elif isinstance(bc, str):
                            error_text = bc[:100]
                        r["tool_error_details"].append({
                            "turn": current_turn,
                            "error": error_text,
                        })

        # Assistant responses
        if etype == "assistant" and "message" in obj:
            msg = obj["message"]
            content = msg.get("content", [])
            usage = msg.get("usage", {})
            r["responses"] += 1

            # Thinking
            has_thinking = False
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "thinking":
                            has_thinking = True
                        if block.get("type") == "tool_use":
                            name = block.get("name", "unknown")
                            r["tool_counts"][name] += 1
                            inp = block.get("input", {})
                            if name in ("Task", "Agent"):
                                tid = block.get("id", "")
                                if tid:
                                    subagents.add(tid)
                            fp = inp.get("file_path", inp.get("path", ""))
                            if fp:
                                fname = os.path.basename(fp)
                                if name in ("Edit", "Write", "MultiEdit"):
                                    r["files_edited"][fname] += 1
                                else:
                                    r["files_read"][fname] += 1
            if has_thinking:
                r["thinking_count"] += 1

            # Usage
            if usage:
                inp_t = usage.get("input_tokens", 0)
                cache_r = usage.get("cache_read_input_tokens", 0)
                cache_c = usage.get("cache_creation_input_tokens", 0)
                out_t = usage.get("output_tokens", 0)
                r["tokens"]["input"] += inp_t
                r["tokens"]["cache_read"] += cache_r
                r["tokens"]["cache_creation"] += cache_c
                r["tokens"]["output"] += out_t
                ctx = inp_t + cache_r + cache_c + out_t
                last_context = ctx
                r["context_history"].append(ctx)
                r["per_response"].append({
                    "turn": current_turn,
                    "ctx": ctx,
                    "input": inp_t,
                    "cache_read": cache_r,
                    "output": out_t,
                    "timestamp": ts,
                })

        # Compaction
        if (etype == "summary" or
                (etype == "system" and obj.get("subtype") == "compact_boundary")):
            r["compact_count"] += 1
            r["context_history"].append(None)
            ctx_before = last_context
            r["compact_events"].append({
                "turn": current_turn,
                "context_before": ctx_before,
                "turns_since_last": r["turns_since_compact"],
                "timestamp": ts,
            })
            r["turns_since_compact"] = 0

    r["subagent_count"] = len(subagents)
    r["last_context"] = last_context
    return r


def get_pricing(model):
    """Get pricing dict for a model string."""
    for key, p in MODEL_PRICING.items():
        if key in model:
            return p
    return MODEL_PRICING["claude-sonnet-4-6"]


def calc_cost(tokens, pricing):
    """Calculate costs from token counts and pricing."""
    c_input = tokens["input"] * pricing["input"] / 1_000_000
    c_cache = tokens["cache_read"] * pricing["cache_read"] / 1_000_000
    c_output = tokens["output"] * pricing["output"] / 1_000_000
    return {
        "input": c_input,
        "cache_read": c_cache,
        "output": c_output,
        "total": c_input + c_cache + c_output,
    }


def format_duration(start_ts, end_ts=None):
    """Format duration between two ISO timestamps."""
    try:
        start = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
        if end_ts:
            end = datetime.fromisoformat(end_ts.replace("Z", "+00:00"))
        else:
            end = datetime.now(timezone.utc)
        secs = int((end - start).total_seconds())
        h, m = secs // 3600, (secs % 3600) // 60
        return f"{h}h {m}m" if h > 0 else f"{m}m"
    except Exception:
        return "unknown"


def format_tokens(n):
    """Format token count as human-readable."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def get_transcript_path():
    """Get transcript path from argv or auto-detect."""
    if len(sys.argv) > 1:
        return sys.argv[1]
    return find_transcript()
