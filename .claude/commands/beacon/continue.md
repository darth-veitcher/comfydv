---
description: Determine the next BEACON step from repo state and run it. Proposes-then-confirms by default; pass --auto for unattended build-loop steps; pass --full-auto for fully autonomous operation (agent-trio resolves judgment calls via product+engineering subagents).
argument-hint: [--auto | --full-auto]  — --auto skips confirmations on reversible steps; --full-auto also dispatches /git:pr and uses agent-trio deliberation for all judgment calls
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Task, TodoWrite
---

You're advancing this project one BEACON step. First orient (reusing
`/beacon.status`'s state-read verbatim — the decision ladder lives there, not
here), then act on the recommendation.

## Parse arguments

The user's invocation:

$ARGUMENTS

- If `--full-auto` is present, you're in **full-auto mode** (see `## Act → --full-auto`).
- If `--auto` is present (and not `--full-auto`), you're in **auto mode** (see `## Act → --auto`).
- Otherwise you're in **default mode** — propose, then wait for a yes.

## Orient

@.claude/commands/beacon/status.md

Run that orientation now. It ends with a `Recommended next: <command>` line — that
command is what you're about to act on. Don't re-derive the decision; reuse it.

## Act

### Default mode — propose, then confirm

1. State the recommended next step and a one-line rationale (pull both straight
   from the `/beacon.status` footer).
2. Ask: **"Run this now?"** Wait for the user.
3. On yes, dispatch it:
   - A `/beacon.*` or `/git:*` step → invoke that slash command.
   - A `beacon …` CLI step → run it via Bash.
   Then stop. One `/beacon.continue` = one step. The user re-runs to take the next.
4. On no, stop without acting.

### --auto mode — unattended, for `/loop`

In `--auto` you act without asking, but **only on reversible, non-interactive
build-loop steps**:

- ✅ Auto-dispatch: `/beacon.plan`, `/beacon.tasks`, `/beacon.implement`,
  `/beacon.review`, `/beacon.audit` (read-only — it only reports coverage gaps
  and suggests `beacon epic stub` lines; it creates nothing).
- ⛔ **STOP and report** (these need a human or are outward-facing / hard to
  reverse — never fire them unattended): `/beacon.seed`, `/beacon.epics`,
  `beacon epic new`, `/beacon.specify` (someone must choose the feature),
  `/git:pr`, `/git:release`,
  `beacon epic finish`, any `beacon doctor` FAIL that needs a judgment call, or
  an `epic-dependency-gate` WARN (the current epic's dependency hasn't shipped
  yet — advance the blocking epic first, not this one).
- Also stop when the recommendation is **"You're clear — nothing pending."**

When you stop, say plainly *why* and *what the human needs to do* — that message is
the loop's output.

After auto-dispatching a step, re-run the **Orient** section and continue the loop
until you hit a stop condition above. This makes `/loop 10m /beacon.continue --auto`
safe: it drives the build loop forward and parks at every gate that wants a person.

### --full-auto mode — unattended with agent-trio self-governance

`--full-auto` is a superset of `--auto`. In this mode **the agent trio is the
human**: you (the orchestrator) invoke `beacon-product` and `beacon-engineering`
as independent subagents to resolve gates that `--auto` parks at — the same
two-perspective deliberation a human product+engineering review would apply.

**Additional auto-dispatches beyond `--auto`:**

- ✅ `/git:pr` — open the PR without asking.
- ✅ `beacon epic finish` — if `beacon epic status <slug>` confirms all specs
  are Done/Shipped, archive it. The condition is objective; no deliberation needed.
- ✅ `epic-dependency-gate` WARN, `beacon epic new`, `/beacon.epics`,
  `/beacon.specify`, any `beacon doctor` FAIL needing a judgment call — resolve
  via **agent-trio deliberation** (see below).

**Agent-trio deliberation (for judgment gates):**

When you hit a gate requiring strategic or engineering judgment:

1. Invoke `beacon-product` and `beacon-engineering` as **independent** subagents
   with no shared context, scoped to the specific question. Frame it concretely:
   "Given the SEED artefacts, should we proceed with X or first address Y?"
   Their independence is what makes their agreement meaningful.
2. Synthesise their verdicts inline:
   - Both aligned → **act**.
   - Either negative or conflicted → **STOP** and surface the disagreement
     exactly as `--auto` does: say why and what the human needs to resolve.

This mirrors `/beacon.align` but scoped to a single decision rather than a full
project review.

**Hard stops (the only two that remain):**

- ⛔ `/git:release` — irreversible external side effect (published package/tag
  cannot be undone). Hard stop regardless of agent verdicts.
- ⛔ **"You're clear — nothing pending."** — correct loop termination.

When you stop, say why and what the human needs to do, exactly as `--auto` does.

## Graceful degradation — SpecKit not installed

`/beacon.continue` and `/beacon.status` always install, but the
`/beacon.{specify,plan,tasks,implement}` wrappers are SpecKit-gated. If the
recommended step is one of those and the wrapper file is absent
(`.claude/commands/beacon/<verb>.md` missing), either fall back to the raw
`/speckit-<verb>` command if SpecKit's own skills are present, or tell the user:

> SpecKit isn't installed. Install it, then `beacon upgrade`, to enable the
> `/beacon.*` spec wrappers. (See `beacon help commands`.)
