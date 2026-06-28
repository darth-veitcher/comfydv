---
description: Refresh ROADMAP.md from live BEACON data, summarise epic health, and suggest next steps. Pass `render` to also produce ROADMAP.html.
argument-hint: [render]  — also produce ROADMAP.html
allowed-tools: Bash, Read
---

You're refreshing the BEACON roadmap and summarising the current state.

The user's invocation:

$ARGUMENTS

## Step 1 — Regenerate

Run:
```bash
beacon roadmap export
```

This includes the most-recently-completed epics by default (controlled by `roadmap_done_limit` in the manifest, defaulting to 3). Pass `--exclude-done` to suppress Done/archived epics.

If the user passed `render` as an argument (i.e. `$ARGUMENTS` contains the word `render`), also run:
```bash
beacon roadmap render
```

## Step 2 — Summarise

Read the just-written `ROADMAP.md` and report concisely:

- **Epic counts** by status: Active / Planning / Paused / Done (including any archived epics shown)
- **Fidelity** for each epic — show the badge (`S+/S?  A+/A?  T:N%`) and flag any that are `S?` (no specs) or `A?` (no ADRs)
- **In-flight bullets** — how many worktrees have active bullets and which epics they're attached to
- **Roadmap coverage** — fraction of Active epics that have both specs and ADRs filled in

Keep the summary to a tight table or bullet list — this is a health snapshot, not a narrative.

## Step 3 — Next steps

Close with 2–4 concrete suggestions ranked by impact:

| Condition | Suggestion |
|---|---|
| Epic in Planning for more than one sprint with no specs | Mark Active or archive: `beacon epic archive <slug>` |
| Active epic with no specs | `/beacon.specify <slug> "<first feature>"` |
| Active epic with 0% task completion | Investigate — may need `/beacon.plan` |
| No epics at all | Start the first initiative: `beacon epic new <slug> --title "…"` |
| ROADMAP.html not requested but HTML would be useful | Mention `beacon roadmap render` |

Give at most the top 3 items; don't enumerate every epic if the list is long.
