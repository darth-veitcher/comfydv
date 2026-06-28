---
description: Run SpecKit's tasks command, then enforce BEACON's test-first discipline — reframe tests as contracts, pair test/impl tasks, and scaffold .feature files from the spec's scenarios (default; pass --no-bdd to skip).
argument-hint: [--no-bdd] (skip .feature scaffolding — otherwise no arguments; operates on the current spec branch)
allowed-tools: Bash, Read, Write, Edit, Glob
---

## SpecKit's tasks skill (inlined verbatim)

@.claude/skills/speckit-tasks/SKILL.md

## BEACON post-step — make test-first discipline real

SpecKit's template frames tests as *optional polish* and lists them in a
separate "Tests for User Story N" block above an "Implementation for User
Story N" block. That ordering is descriptive only — nothing stops an agent
from flattening it into one commit, and the discipline that's the whole point
of the ordering never gets invoked. BEACON fixes that here.

### 1. Tests are first-class, not optional

After SpecKit writes `specs/<NNN-slug>/tasks.md`, read `specs/<NNN-slug>/spec.md`.

**Tests are first-class deliverables for any spec that carries Acceptance
Scenarios or Success Criteria.** Mark a spec test-exempt only when the work is
purely documentation, configuration, or a single trivial-and-irreversible
change. If `tasks.md` was generated without test tasks for a spec that *does*
have acceptance scenarios, add them — do not treat their absence as a choice.

### 2. Rewrite each user story into interleaved TDD pairs

When the spec has Acceptance Scenarios, rewrite each user-story phase so the
test and its implementation sit **adjacent as a pair**, rather than in two
separate "Tests" / "Implementation" sections:

```diff
-### Tests for User Story 1
-- [ ] T010 [US1] Unit-test X in tests/...
-- [ ] T011 [US1] Integration-test Y in tests/...
-
-### Implementation for User Story 1
-- [ ] T012 [US1] Implement X in src/...
-- [ ] T013 [US1] Implement Y in src/...
+### User Story 1 — TDD pairs
+- [ ] T010-T [US1] Write FAILING test for X in tests/...   (red)
+- [ ] T010-I [US1] Implement X so T010-T passes in src/...  (green)
+- [ ] T011-T [US1] Write FAILING test for Y in tests/...   (red)
+- [ ] T011-I [US1] Implement Y so T011-T passes in src/...  (green)
```

The visual pairing makes it hard to silently flatten the discipline into one
commit. The `-T` / `-I` suffix is a convention `beacon doctor` and
`/beacon.implement` reason about: a `-T` task is committed on its own (failing)
before its `-I` partner. Keep `[P]` parallel markers only on tasks that are
genuinely independent — a `-I` task is never parallel with its own `-T`.

**Deferred follow-ups.** A task that is real work but legitimately out of *this*
bullet's scope — e.g. it depends on a fixture a later bullet ships — gets a
`[-]` (or `[d]`) checkbox instead of `[ ]`, with a brief `_Deferred — why_`
note (issue #84):

```
-- [ ] T020 Run the slow accuracy benchmark   (waits on a fixture)
++ [-] T020 Run the slow accuracy benchmark _Deferred — depends on T010's fixture, lands in a follow-up bullet._
```

`beacon bullet finish` skips `[-]` tasks instead of flipping them to `[x]`, so
`tasks.md` keeps meaning what you wrote; `beacon doctor` reports them as
known-deferred follow-ups (held under `--strict`), distinct from a stray `[ ]`
left behind as tech debt. Plain `[ ]` keeps its old behaviour — the marker is
opt-in.

### 3. Scaffold executable scenarios from the spec (default; `--no-bdd` to skip)

Unless the user passed `--no-bdd`, turn the spec's Given–When–Then acceptance
scenarios into executable witnesses. This is the default so the discipline holds
on every path — including unattended `/beacon.continue --auto` loops, which
dispatch `/beacon.tasks` with no arguments. Skip this step only when `--no-bdd`
is present or the spec is test-exempt (see step 1):

1. For each acceptance scenario in `spec.md`, write a Gherkin scenario
   **verbatim** into `specs/<NNN-slug>/features/<usN_slug>.feature`, plus
   placeholder step definitions in the project's test tree:

   ```gherkin
   # specs/001-tier1-table-profiler/features/us1_column_profile.feature
   Feature: US1 — Column-level profile

     Scenario: Profile a small CSV with mixed column types
       Given a CSV file with 4 rows and 4 columns
       When the profiler runs against the CSV
       Then the profile contains 4 column entries
       And each column entry carries an inferred type
   ```

2. Have the `-T` test tasks in `tasks.md` reference the scenario **by name**
   ("Implement step defs for US1 — Column-level profile") instead of describing
   the assertion imperatively. This gives `spec.md → .feature → test`
   traceability that the `spec-bdd-coverage` doctor check can verify.

### 4. Confirm

End by noting which user stories were paired, whether `.feature` scaffolding was
written (or skipped via `--no-bdd`), and reminding the user that `beacon doctor`
now runs two gates against
this discipline: `spec-bdd-coverage` (every scenario has a witness) and
`tdd-commit-discipline` (no tests + implementation in the same commit). Both
FAIL under `beacon doctor --strict`.
