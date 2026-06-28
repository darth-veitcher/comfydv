# Work/ — Transient Workspace

This directory is a **scratchpad**. Everything here is temporary by design.

## Lifecycle

```
During work   →  Create freely in Work/
After commit  →  Promote important insights to ADRs; delete the rest
After merge   →  Delete sessions/*; prune planning/*; delete analysis/* (if ADR written)
```

**Rule:** If it matters long-term, it belongs in `ADRs/`, `Background/`, or the codebase. If it lives only in `Work/`, it will be lost.

## Subdirectories

| Directory | Contents | When to delete |
|-----------|----------|----------------|
| `sessions/` | Session summaries, daily notes | After merge to develop |
| `planning/` | Feature planning docs, future-features.md | After the feature ships |
| `analysis/` | Architecture analysis, spike results | After promoted to ADR, or if stale |

## Cleanup command

Run after a release PR merges:

```bash
cd project-management/Work
rm -rf sessions/*
rm -rf planning/*   # keep only active WIP
rm -rf analysis/*   # only if ADRs are written
```

The `post-merge` git hook will remind you if session files are older than 2 weeks.

## Session file naming

`sessions/YYYY-MM-DD-[bullet-or-topic].md`

Example content:
```markdown
# Session: 2026-01-15 — Bullet #3: Azure DevOps integration

## Goal
Wire up MCP azure-devops server to create work items from Claude Code

## What I did
- Installed @tiberriver256/mcp-server-azure-devops
- Configured in .claude/settings.json
- Tested with /azure:devops-task create task: test item

## Decisions made
- Using PAT not service principal for now — ADR-002 written

## Blockers
- None

## Tomorrow
- Bullet #4: Add Fabric query support
```
