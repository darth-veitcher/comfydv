---
description: Adversarial engineering review — challenges feasibility, missing prerequisites, dependency ordering, and scope. Use before building starts to stress-test the plan.
argument-hint: (no args) full review  |  <epic-slug> scoped to one epic  |  scope  decomposition + scope risks only
allowed-tools: Bash, Read, Glob, Grep
---

Invoke the `beacon-engineering` subagent to stress-test whether this project's plan is actually executable.

The argument is:

$ARGUMENTS

## Step 1 — Determine mode

Parse `$ARGUMENTS`:

- **Empty** → full engineering review (all four lenses)
- **`scope`** → decomposition and scope sizing only: skip feasibility and dependency checks; focus on whether epics are independently shippable and specs are tracer-bullet sized
- **Anything else** → treat as an epic slug and scope the review to that epic

## Step 2 — Invoke the subagent

Spawn the `beacon-engineering` subagent.

### Full review (no args)

No extra constraints. The subagent reads the full artefact tree and reports across all four lenses: feasibility, missing prerequisites, dependency ordering, and scope.

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

If found, direct the subagent: scope the **Feasibility concerns** and **Dependency ordering problems** sections to `<epic-slug>` and its owned specs. The **Missing prerequisites** and **Scope risks** sections remain project-wide — a missing prerequisite might block multiple epics, not just the one in scope.

### Scope mode (`scope`)

Direct the subagent to skip the **Feasibility concerns**, **Missing prerequisites**, and **Dependency ordering problems** sections entirely. Focus only on **Scope risks** and **Recommended adjustments** — are epics independently shippable and specs tracer-bullet sized?

## Step 3 — Print the report

Print the subagent's output verbatim.

Then add one line:

> Re-run anytime: `/beacon.engineering`
