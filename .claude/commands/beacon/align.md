---
description: Joint product + engineering review — runs both lenses independently and synthesises agreements, disagreements, and a joint recommendation. Use after /beacon.epics to validate the plan before building starts.
argument-hint: (no args) full project  |  <epic-slug> scoped to one epic
allowed-tools: Bash, Read, Glob, Grep
---

Run the `beacon-product` and `beacon-engineering` subagents independently against the same artefact tree, then synthesise their findings into a joint recommendation. The combination surfaces what either lens alone would miss: goals that can't be built, or executable plans that are building the wrong things.

The argument is:

$ARGUMENTS

## Step 1 — Check preconditions (silently)

Run:

```bash
beacon seed
```

If the result is not green (placeholders remain in the problem statement), stop:

```
beacon seed is not green — the problem statement has unfilled placeholders.
Run /beacon.seed first. There is no north star to align against until it's filled.
```

If the argument is an epic slug (not empty), verify it exists:

```bash
test -f project-management/Roadmap/epics/<slug>.md || echo "NOT FOUND"
```

If not found, stop with a clear error and suggest `beacon epic list`.

## Step 2 — Run both agents independently

Invoke `beacon-product` and `beacon-engineering` as subagents. They run with the same scope but share no context with each other — each reads the artefacts fresh. That independence is the point: agreements between two agents that didn't collaborate are high-confidence signals.

For **full review** (no args): give each subagent no scope constraint.

For **scoped review** (`<epic-slug>`): direct each subagent to scope its grounding/feasibility/sequencing checks to that epic, while keeping momentum, missing-prerequisite, and horizon-risk checks project-wide.

Present both outputs under clearly labelled headers:

```
---
## Product perspective  (/beacon.product)

<beacon-product output verbatim — Trajectory line included>

---
## Engineering perspective  (/beacon.engineering)

<beacon-engineering output verbatim — Build-readiness line included>

---
```

## Step 3 — Synthesise

After both outputs, add a synthesis block. Do not spawn another subagent for this — synthesise inline from the two reports you just received.

```
## Alignment synthesis

**Where they agree**
- <Finding raised by both agents independently. These are the highest-confidence signals — treat them as definite. If there are none, say "No overlapping findings — the two perspectives are complementary rather than confirmatory.">

**Where they differ**
- Product says: <what beacon-product said about topic X>
  Engineering says: <what beacon-engineering said about the same topic>
  → Resolution: <one concrete action that addresses both perspectives>

**Joint recommendation**
<The single most important thing to do right now, synthesised from both perspectives. One sentence. Name the exact command or action.>
```

**If both verdicts are positive** (`Trajectory: on course` + `Build-readiness: ready`), skip the Agree/Differ structure and print:

> Both perspectives agree: the plan is sound and executable.
> Start with `/beacon.specify <first-epic-slug> "<first-feature-description>"`.

**If the verdicts conflict** (e.g., product says on course but engineering says blocked), highlight this explicitly:

> ⚠ The two perspectives disagree on readiness — product sees the goals as sound but engineering has identified a blocker. Resolve the engineering finding before starting build work.

## Step 4 — Footer

> Re-run anytime: `/beacon.align`
