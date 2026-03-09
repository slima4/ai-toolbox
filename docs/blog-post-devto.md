---
title: I built a real-time dashboard for Claude Code because I kept losing track of my sessions
published: false
tags: claudecode, ai, python, opensource
cover_image: https://raw.githubusercontent.com/slima4/claudeui/main/docs/social-card.png
---

Claude Code has a 200k token context window but gives you zero visibility into how much of it you've used — until auto-compaction kicks in and wipes half your context. I got tired of that surprise, so I built ClaudeUI.

## The problem

If you use Claude Code daily, you've probably hit these:

- Auto-compaction fires mid-task and you lose context
- No idea how much a session is costing you
- Can't tell which files Claude has been touching
- No way to compare sessions or track patterns over time

Claude Code is a powerful tool, but it's a black box. You type, it works, and you hope for the best.

## What ClaudeUI does

It's a collection of tools that plug into Claude Code and give you full visibility:

**Statusline** — a real-time status bar that sits at the bottom of Claude Code:

```
 0110100 Opus 4.6 │ ████████░░░░░░░░░░░░ 42% 65.5k/200.0k │ ~24 turns left │ $2.34 │ 12m │ 0x compact
 1001011 my-project │ main +42 -17 │ 18 turns │ 5 files │ 0 err │ 82% cache │ 4x think │ ~$0.13/turn
 0110010 read config.ts → edit config.ts → bash npm test → edit README.md │ config.ts×2 README.md×1
```

Context usage, cost, cache ratio, git diff, tool trace, compaction prediction — all live. There's also a compact 1-line mode if you prefer minimal.

**Live Monitor** — open a second terminal and get a full dashboard:

```
$ claude-ui-monitor
```

![ClaudeUI Monitor — live session dashboard](https://raw.githubusercontent.com/slima4/claudeui/main/docs/monitor-screenshot.png)

Context sparkline with compaction history, cost breakdown with cache savings, per-turn activity (tools, files, errors), session-wide stats, and a scrollable log viewer with filters. It even tracks agent spawns and their results. The matrix rain header pauses when Claude is idle.

**Hooks** — automatic context injected into your sessions:

- Session start: shows which files you've been editing recently across sessions
- After edit: warns you about reverse dependencies ("4 files import this module")
- Before edit: flags high-churn files ("config.ts edited 43 times in 5 sessions — maybe refactor?")

**Session Stats** — post-session analytics:

```
$ claude-stats --days 7 -s
```

Cost breakdown, token sparklines, tool usage charts, file activity heatmaps. See which sessions burned the most tokens and why.

**Session Manager** — browse and compare sessions:

```
$ claude-sessions list
$ claude-sessions diff abc123 def456
```

Side-by-side comparison of cost, duration, tools used, and file activity between any two sessions.

**Slash Commands** — deep reports without leaving Claude Code:

```
/ui:session    # full session report
/ui:cost       # cost deep dive
/ui:perf       # tool efficiency analysis
/ui:context    # context window predictions
```

## How it works

Everything runs by parsing Claude Code's transcript JSONL files from `~/.claude/projects/`. No API keys, no external services, no dependencies — just Python 3.8+ and the standard library.

The statusline uses Claude Code's `statusLine` config to run a Python script that reads session metadata from stdin and the transcript file from disk. It does two passes: a reverse pass to find current context size, and a forward pass to accumulate costs and activity.

The hooks use Claude Code's hooks system to run scripts on events like `SessionStart`, `PreToolUse`, and `PostToolUse`.

The monitor watches the transcript file for changes and redraws when it detects new content.

## Install

One command:

```bash
curl -sSL https://raw.githubusercontent.com/slima4/claudeui/main/install.sh | bash
```

It sets up everything — statusline, hooks, slash commands, and CLI tools. The installer asks you to pick full or compact mode for the statusline. You can switch anytime with `claude-ui-mode compact` or `claude-ui-mode full`.

To uninstall: `claude-ui-uninstall`

## What I learned

Building tools that parse another tool's internal format is fragile by nature. Claude Code's transcript format isn't documented, so I had to reverse-engineer it by reading JSONL files and figuring out the structure. It works well today, but could break with any Claude Code update.

The other challenge was performance. The statusline runs on every refresh, so it needs to parse the transcript fast. For long sessions with thousands of entries, the reverse-pass-first approach helps — you find the current context size quickly without reading the entire file sequentially.

## Links

- **Website**: [slima4.github.io/claudeui](https://slima4.github.io/claudeui/)
- **GitHub**: [github.com/slima4/claudeui](https://github.com/slima4/claudeui)

If you use Claude Code and want more visibility into your sessions, give it a try. Issues and PRs welcome.
