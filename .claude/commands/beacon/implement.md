---
description: Run SpecKit's implement command and refresh the parent epic's rollup when the spec completes.
argument-hint: [spec-slug] — defaults to the current spec branch; pass NNN-slug to continue a sharded spec from a non-spec branch
allowed-tools: Bash, Read, Write, Edit, TodoWrite, Glob, Grep
---

## Resolve the target spec

A spec usually ships from its own `NNN-slug` branch, and with no argument this
command operates on that current spec branch (SpecKit's own detection). But a
large spec often shards across several PRs off `feature/`/`fix/` branches, each
ticking a slice of the *same* `tasks.md` (see `/beacon.status`'s decision ladder).
To continue such a spec from a non-spec branch, pass its slug:

```
/beacon.implement 005-memgraph-storage-substrate
```

The target spec is, in order: the `$ARGUMENTS` slug if given; else the spec named
by the current spec branch; else the `specs/NNN-*` folder matching a leading
`NNN-` token in the current branch name. Operate on **that** spec's
`specs/<slug>/tasks.md` throughout — the TDD discipline below and the rollup
refresh after both key off the resolved `<slug>`, not the branch name.

## Before you start — BEACON TDD commit discipline

SpecKit executes tasks in order but says nothing about commit boundaries, so an
agent can write a story's tests *and* implementation in one pass and commit them
together — which means the tests never went red and can only confirm the code's
*current* behaviour, not catch its absence. Don't do that. For every TDD pair in
`tasks.md` (the `-T` / `-I` convention `/beacon.tasks` emits):

1. **Red.** Implement the `-T` task only — write the test, run it, watch it
   **fail** for the right reason. Commit that on its own:
   `git commit -m "test(US1): failing test for column profile (T010-T)"`.
2. **Green.** Implement the `-I` task until the `-T` test passes. Commit
   separately: `git commit -m "feat(US1): column profile (T010-I)"`.
3. **Refactor** under green, committing as needed.

Never let a single commit add a brand-new test file *and* a brand-new source
file — that's exactly the no-red-phase pattern `beacon doctor`'s
`tdd-commit-discipline` check flags (FAIL under `--strict`). If the spec has
`.feature` files (scaffolded by `/beacon.tasks` by default), the `-T` step is "make this
scenario pass"; `spec-bdd-coverage` confirms every spec.md Given/When/Then has a
witness.

## SpecKit's implement skill (inlined verbatim)

@.claude/skills/speckit-implement/SKILL.md

## After implementation — BEACON rollup refresh

Once SpecKit reports the tasks are complete (all `[ ]` in `tasks.md` flipped to `[x]`):

1. **Find the parent epic.** Read `specs/<NNN-slug>/.beacon.toml`:
   ```bash
   cat specs/<NNN-slug>/.beacon.toml
   ```
   The file contains `epic = "<slug>"`. If it's missing, the spec was never backlinked — run `beacon link-spec <NNN-slug> --epic <slug>` first.

2. **Recompute the rollup.**
   ```bash
   beacon epic refresh <epic-slug>
   ```
   This prints owned-spec counts (complete / in flight / missing) and flags if the epic is ready to archive.

3. **If `beacon epic refresh` reports all owned specs complete**, prompt the user to archive the epic once the spec branch merges to develop / main:
   ```bash
   beacon epic finish <epic-slug>
   ```
   (`epic finish` refuses while any owned spec branch is still live — it's safe to suggest.)

This closes the Engineering→Product status loop: as soon as the last spec ships, Product sees the rollup and can sign the epic off without needing a meeting.
