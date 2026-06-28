---
description: Read the repo's BEACON state — current phase, health, active bullet/epic — and report the single recommended next step. Consumed by /beacon.continue.
argument-hint: (no arguments — operates on the current worktree)
allowed-tools: Bash, Read, Glob, Grep
---

You're reporting where this project sits in the BEACON lifecycle
(SEED → DESIGN → BUILD → SHIP) and what the single next step is. You don't *do*
the next step — you name it. `/beacon.continue` consumes this report to act.

Compose the status primitives BEACON already ships; don't reimplement their
logic. Tolerate non-zero exits (they're signal, not failure).

## Orientation

Run these read-only probes and read their output:

1. **Git position.**
   ```bash
   git rev-parse --abbrev-ref HEAD     # current branch
   git status --porcelain              # dirty? (uncommitted work)
   git log --oneline -8                # recent history
   # PR-merged probe: 0 == this branch already landed on the trunk upstream.
   git merge-base --is-ancestor HEAD origin/main; echo "merged=$?"
   ```

2. **SEED gate.** `beacon seed` — FAILs while the problem statement / architecture
   / roadmap still carry template placeholders. Green means SEED is signed off.

3. **Health.** `beacon doctor` — the 15 semantic checks. Note every `FAIL` and
   `WARN` by name (e.g. `epic-adr-coverage`, `tdd-commit-discipline`). The summary
   footer reads `ok=N warn=N fail=N`.

4. **Active bullet.** `beacon bullet status` — the current worktree's bullet, or a
   note that none is started. `beacon bullet list` if you want the cross-branch view.

5. **Epics + rollup.** `beacon epic list --detailed` — active epics and their
   owned-spec rollup (complete / in flight / missing).

6. **Spec context.** Find the spec this branch is working, then inspect its tasks.
   Two ways a branch points at a spec:
   - **Spec branch** (`NNN-slug`, e.g. `003-table-profiler`) — the spec is
     `specs/<branch>/`.
   - **Non-spec continuation branch** (`feature/`/`fix/`/… on a sharded spec) — a
     large spec often ships across several PRs off `feature/` branches, each
     ticking a slice of the *same* `tasks.md`. Resolve the spec the active bullet
     (step 4) is continuing, in this order, stopping at the first that names exactly
     one spec: (a) a leading `NNN-` token in the branch name matched to a
     `specs/NNN-*` folder (e.g. `feature/005-phase4-vector-ops` → `specs/005-…`);
     else (b) the bullet's `--epic` whose rollup (step 5) lists a single in-flight
     spec; else (c) a spec slug named in the bullet title. If none resolves a
     single spec, there's no spec continuation — fall through to the plain non-spec
     bullet rows.

   For whichever spec resolved, inspect `specs/<slug>/`:
   - Is there a `spec.md`? a `plan.md`? a `tasks.md`?
   - In `tasks.md`, are there active `[ ]` / in-progress `[~]` task lines, is
     everything `[x]`, or are the only leftovers deferred `[-]` / `[d]` follow-ups
     (out of this bullet's scope — shippable, not work in flight)?

7. **SpecKit presence.** Check whether `.claude/skills/speckit-specify/SKILL.md`
   (or `.claude/commands/beacon/specify.md`) exists. When absent, the
   `/beacon.{specify,plan,tasks,implement}` wrappers aren't installed and the next
   step must fall back to raw `/speckit-*` or a "install SpecKit + `beacon upgrade`"
   nudge.

## Phase + next-step decision

Walk this ladder top-to-bottom and stop at the **first** row that matches. That
row is the recommendation. (This mirrors the phase gates in `beacon help phases`.)

| State | Phase | Recommended next step |
|---|---|---|
| No BEACON manifest (`project-management/.beacon/init-options.json` absent) | — | `beacon init` — this isn't a BEACON project yet |
| `beacon doctor` has a `FAIL` unrelated to phase progress (a broken window) | (current) | Fix that check first — name it. Don't advance over a red gate |
| `beacon seed` not green (placeholders remain) | SEED | `/beacon.seed` |
| SEED green, no epics declared | DESIGN | `/beacon.epics` — plan the initiative roadmap with a PM guide |
| On integration/default branch (`main` / `develop`), epic exists with owned stubs not yet broken out into real specs | DESIGN | `/beacon.audit <slug>` — confirm the epic's stubs/specs cover every Success criterion before building (default-on *design* moment; tune via doctor.toml `[audit] moments`) |
| On integration/default branch (`main` / `develop`), epic(s) exist | DESIGN→BUILD | `/beacon.specify <epic> <feature>` (with SpecKit) **or** `/git:feature <name>` + `beacon bullet start` for non-spec work |
| Branch already merged into `main` (PR landed), bullet still active | SHIP | `beacon bullet finish && git switch main && git pull` |
| Spec branch, `spec.md` present but no `plan.md` | DESIGN | `/beacon.plan` |
| Spec branch, `plan.md` present but no `tasks.md` | DESIGN | `/beacon.tasks` |
| Spec branch, `tasks.md` has active `[ ]` / `[~]` tasks | BUILD | `/beacon.implement` |
| Spec branch, every task `[x]` or deferred `[-]` / `[d]`, diff not yet reviewed | BUILD→SHIP | `/beacon.review` (deferred follow-ups ship as known debt) |
| Review clear, branch ahead of base, no PR open | SHIP | `/git:pr` |
| Non-spec feature branch (`feature/` `fix/` `chore/` `docs/`), no bullet started | BUILD | `beacon bullet start "<title>" [--epic <slug>]` |
| Non-spec branch, bullet active, the bullet's resolved spec (step 6) has open `[ ]` tasks | BUILD | `/beacon.implement <slug>` — continue the sharded spec; name the spec from step 6 |
| Non-spec branch, bullet active, work done & reviewed, not yet merged | SHIP | `/git:pr` |
| Epic's owned specs all complete and merged | SHIP | `/beacon.audit <slug>` then `beacon epic finish <slug>` — the audit (default-on *ship* moment) catches a Success criterion no spec ever covered, which the placeholder gate can't see |
| Everything green, nothing in flight | — | "You're clear — nothing pending." |

If two rows could both apply, prefer the earlier one — broken windows before
progress, and the earliest unfinished phase artifact before later ones.

## Report

Give a short narrative (2–4 sentences): where the project is, what's healthy,
what's blocking. Then close with this exact-shaped footer so `/beacon.continue`
and humans can parse it at a glance:

```
Phase: <SEED|DESIGN|BUILD|SHIP|—>
Health: doctor ok=<n> warn=<n> fail=<n>  ·  seed: <green|not green>
Recommended next: <command>   — <one-line why>
```

The recommendation is advice, not an order — the user decides whether to take it.
