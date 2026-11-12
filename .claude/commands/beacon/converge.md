---
description: Run SpecKit's converge command to close the gap between a spec's intent and the code that claims to implement it — appending any remaining work as new tasks before review.
argument-hint: [spec-slug] — defaults to the current spec branch; pass NNN-slug to converge a sharded spec from a non-spec branch
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

## Resolve the target spec

Converge assesses **one** spec's code against its own artefacts. A spec usually
ships from its own `NNN-slug` branch, and with no argument this command operates
on that current spec branch (SpecKit's own detection). A large spec that shards
across several PRs off `feature/`/`fix/` branches (see `/beacon.status`'s
decision ladder) is converged from a non-spec branch by passing its slug:

```
/beacon.converge 005-memgraph-storage-substrate
```

The target spec is, in order: the `$ARGUMENTS` slug if given; else the spec named
by the current spec branch; else the `specs/NNN-*` folder matching a leading
`NNN-` token in the current branch name.

## Step 1 — Confirm the spec is at the converge gate

Converge is the **between implement and review** step. It reads `spec.md`,
`plan.md`, and `tasks.md` as the sole source of intent and checks the code
against them. It is only meaningful once `/beacon.implement` has run on the
current `tasks.md` — so before continuing, confirm `specs/<slug>/tasks.md` has
no active `[ ]` / `[~]` tasks left:

```bash
grep -nE '^\s*[-*]\s*\[[ ~]\]' specs/<slug>/tasks.md
```

- **No matches** (every task is `[x]` or deferred `[-]`/`[d]`) → proceed to Step 2.
- **Matches remain** → STOP. Converge appends tasks to a finished list; running
  it with work still open just re-reports what `tasks.md` already says. Finish
  the open tasks first: `/beacon.implement <slug>`.

## Step 2 — Run SpecKit's converge skill

SpecKit's converge skill is inlined verbatim below. Apply it to the resolved
spec. It is **append-only**: its single write is a new `## Phase N: Convergence`
section of new tasks at the bottom of `tasks.md`. It never rewrites existing
tasks, never touches `spec.md`/`plan.md`, and never edits application code. When
the code already satisfies the spec, it leaves `tasks.md` byte-for-byte
unchanged and reports a clean result.

@.claude/skills/speckit-converge/SKILL.md

## Step 3 — Record the converge (required)

**Always run this**, whichever outcome SpecKit reported. Converge writes nothing
on a clean run, so "ran clean" and "never ran" look identical in `tasks.md` unless
we record the fact. The status ladder keys off this marker to move you from
build to review instead of recommending converge forever:

```bash
beacon spec converged <NNN-slug>
```

This writes `converged_at` into `specs/<NNN-slug>/.beacon.toml` — BEACON's own
sidecar, which SpecKit ignores. Run it *before* interpreting the outcome below.

## Step 4 — Interpret the outcome

SpecKit reports one of two outcomes; both are first-class, not error states:

- **`tasks_appended`** — the code has gaps against the spec. Converge appended
  them as new `[ ]` tasks under a `## Phase N: Convergence` header. These are
  **BEACON tasks too**: they carry the same test-first obligation as any other
  task (see `/beacon.tasks`), so hand off with:

  > N gap(s) appended under Phase N of `specs/<slug>/tasks.md`. Continue with
  > `/beacon.implement <slug>` — this is more BUILD, not a review.

  The `converged` marker you just recorded stands; when those tasks are built the
  ladder advances to review without re-converging (one converge pass per spec, by
  design). Re-run `/beacon.converge` by hand if you want a fresh assessment.

- **`converged`** — the implementation satisfies spec, plan, and tasks. Nothing
  was written. This is the bar to cross before review:

  > ✅ Converged. Proceed to `/beacon.review`.

## Step 5 — BEACON note on the traceability convention

SpecKit's converge references each appended task to its origin as
`(gap-type)`. BEACON's `/beacon.tasks` already pairs test/implementation as
`-T` / `-I` tasks; when you next run `/beacon.implement`, apply that same
discipline to any appended convergence task that carries acceptance-scenario
work, so the red/green commit boundary is preserved and
`tdd-commit-discipline` stays green.

Do not run `beacon epic refresh` here — converge changes one spec's task list,
not its shipped status. The rollup refresh belongs to `/beacon.implement`'s
completion step.
