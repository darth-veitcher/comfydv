---
description: Strategic product review — reads the full artefact tree and reports whether active work tracks toward the stated goals and quarter vision. Use when in doubt about direction, sequencing, or scope.
argument-hint: (no args) full review  |  <epic-slug> scoped to one epic  |  steer  forward-looking only
allowed-tools: Bash, Read, Glob, Grep
---

Invoke the `beacon-product` subagent to assess whether this project's active work is tracking toward its stated goals.

The argument is:

$ARGUMENTS

## Step 1 — Determine mode

Parse `$ARGUMENTS`:

- **Empty** → full review (default)
- **`steer`** → forward-looking only: sequencing + horizon risk + next action (skip backward-looking sections)
- **Anything else** → treat as an epic slug and scope the grounding + sequencing checks to that epic

## Step 2 — Invoke the subagent

Spawn the `beacon-product` subagent.

### Full review (no args)

Give the subagent no extra constraints. It will read the full artefact tree and report across all four lenses (grounding, sequencing, momentum, horizon risk).

### Scoped review (`<epic-slug>`)

First verify the epic exists:

```bash
test -f project-management/Roadmap/epics/<slug>.md || echo "NOT FOUND"
```

If not found, stop:

```
No epic found at project-management/Roadmap/epics/<slug>.md.
Run `beacon epic list` to see available epics.
```

If found, direct the subagent: focus the **Grounding gaps** and **Sequencing risks** sections on `<epic-slug>` and its owned specs only. The **Momentum blockers**, **Horizon risk**, and **Recommended next action** sections remain project-wide.

### Steer mode (`steer`)

Direct the subagent to skip the **Grounding gaps** and **Momentum blockers** sections entirely. Focus on: **Sequencing risks**, **Horizon risk**, and **Recommended next action** — the forward-looking view of what to do next and what threatens the quarter vision.

## Step 3 — Print the report

Print the subagent's output verbatim.

Then add one line:

> Re-run anytime: `/beacon.product`
