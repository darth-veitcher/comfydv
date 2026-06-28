---
name: beacon-build
description: BEACON BUILD phase — implement one tracer bullet per session with test-first discipline. Use when the user says "Starting bullet #N", "Working on [task]", or "Implementing [feature from spec]".
---

# Phase 3: BUILD — Execute one tracer bullet at a time

**Purpose:** Implement the tracer bullets from `tasks.md`, one per session. Ship working software daily.

**Entry triggers:** "Starting bullet #N" / "Working on [task]" / "Implementing [feature from spec]"

**Tool:** `/speckit-implement` — executes the tasks in `specs/[feature]/tasks.md`

---

## Session rhythm

### Start of session
1. Fix any broken windows first (failing tests, lint warnings, TODOs) — max 15 min. If it takes longer, create a ticket and park it.
2. Confirm today's epic + bullet: `beacon bullet status` (shows what this worktree is for).
3. Pull latest from `develop`: `git fetch origin && git checkout develop && git pull`
4. Create feature branch: `/git:feature <bullet-description>` (or `/speckit-specify` for a spec-driven feature).
5. Run `beacon bullet start [<title>] [--epic <slug>]` to register the bullet (records an entry in the committed `project-management/.beacon/bullets.toml` for non-spec branches; for spec branches resolves the active task from `tasks.md`).
6. Write the **acceptance test first** (from the acceptance criteria in `spec.md`).
7. Create `project-management/Work/sessions/YYYY-MM-DD-[bullet].md`.

### During implementation
- One bullet per worktree (parallel agents are fine — each in its own worktree). When scope creep appears in the current bullet, write the idea in `project-management/Work/planning/future-features.md` and return to the bullet.
- Test-first: write failing test → implement minimum code → make it pass → refactor.
- Commit after each meaningful increment: `feat(scope): implement [thing]`
- Verify all previous bullets still pass before moving on.

### End of session
1. Run full BEACON quality gates (configured for **Python** — see `manifest.language`):
   ```bash
   uv run ruff check --fix && uv run ruff format
uv run ty check
beacon doctor --strict   # semantic health — fails on placeholders, drift, stale notes
   ```
2. Run `beacon bullet finish` (flips the task done in `tasks.md` for spec branches; drops the `bullets.toml` entry for non-spec).
3. `beacon bullet list` to regenerate the project dashboard.
4. Write any cross-spec decisions as ADRs and link them in the relevant epic's `## ADRs` section (don't leave them in session notes).
5. Open PR to `develop`: `/git:pr`
6. Ask: **"Would I sign my name to this?"**

---

## Quality gates (non-negotiable before marking a bullet done)

- [ ] Acceptance test passes (from the spec's acceptance criteria)
- [ ] All other tests still pass
- [ ] `uv run ruff check` clean
- [ ] `uv run ruff format --check` clean
- [ ] `uv run ty check` clean
- [ ] `beacon doctor --strict` exits 0
- [ ] No new mocks without documented justification
- [ ] Commit messages follow Conventional Commits
- [ ] Can demo the working feature to a non-technical person

> **Optional — re-audit epic coverage as specs land.** On a multi-spec epic you
> can re-run `/beacon.audit <epic>` each time a spec ships, to catch scope that
> drifted out of view. Off by default; enable the *build* moment so the
> `auto-audit` hook nudges you after `beacon spec finish`:
> `[audit] moments = ["design", "ship", "build"]` in `project-management/.beacon/doctor.toml`.

---

## Emergency procedures

**Stuck for >2 hours:**
1. Document the blocker in the session file.
2. Can you fake/stub this part temporarily? Do it and note the debt.
3. Can you split the bullet? Create two smaller ones in `tasks.md`.
4. Does a decision need making? Write an ADR draft.

**Bullet legitimately can't fit in 4h:**
The 2–4h timebox is a forcing function, not a physical law. When the unit of work genuinely can't be split — a non-trivial migration, an integration with a long handshake — apply one of four stubbing strategies:

| Strategy | When |
|---|---|
| **Stub the dependency** | Work depends on an external service; ship today with a Fake, swap for Real tomorrow |
| **Feature-flag the half-implementation** | Partial code path acceptable; gated flag, full impl in the next bullet |
| **Migrate by shadowing** | Data-shape change; write to both old and new, switch reads later, drop old |
| **Hardcoded happy path first** | Big feature with deferrable error handling; ship happy path, add edges later |

Whichever you pick, today's shipped unit must have a passing acceptance test, touch all layers (the stub counts), be visible to the user (even behind a flag), and be deployable as-is. Full guidance in `BEACON.md` under `<bullets_that_will_not_fit>`. **The wrong response is silent**: stretching the bullet to 8h and pretending the constraint didn't apply.

**New bullet breaks an old one:**
1. Revert to last working state.
2. Write an integration test that catches the regression.
3. Fix minimally — do not expand scope.

**Scope creep appearing:**
1. STOP.
2. Write the idea in `Work/planning/future-features.md`.
3. Revert any out-of-scope changes.
4. Finish the current bullet.
