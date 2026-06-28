---
description: Create a SpecKit spec inside a BEACON epic, with cross-spec context auto-injected and the epic↔spec backlink written.
argument-hint: <epic-slug> <feature description>  — e.g. "user-auth OAuth login via Google"
allowed-tools: Bash, Read, Write, Edit, Glob
---

You're creating a SpecKit spec inside a BEACON epic. The user's invocation:

$ARGUMENTS

## Step 1 — Parse arguments

The first whitespace-separated token is the **epic slug**. Everything after is the **feature description**.

Verify the epic exists at `project-management/Roadmap/epics/<slug>.md`. If it doesn't, STOP and tell the user to create it first:

```
beacon epic new <slug> --title "<title>"
```

Epic creation is a BEACON DESIGN-phase activity — the cross-spec ADRs come out of that step, and the spec you're about to create should reference them.

## Step 2 — Load epic context

Read the epic file. Extract:

- **Why now** — strategic context
- **Success criteria** — what "done" looks like at the epic level
- **Non-goals** — what's explicitly out of scope
- **ADRs** — cross-spec architectural decisions that constrain this spec

Carry these into the spec you generate (Step 3). The spec's own Non-goals MUST include the epic's Non-goals; the spec's Success criteria MUST ladder up to the epic's Success criteria. The spec's design choices MUST be consistent with the listed ADRs.

## Step 3 — Run SpecKit's specify command

SpecKit's specify skill is inlined verbatim below. Apply it to the **feature description only** (not the epic slug), with the epic context from Step 2 already in mind.

@.claude/skills/speckit-specify/SKILL.md

## Step 4 — Backlink the new spec to the epic

Once SpecKit's command has created `specs/<NNN-slug>/` and you know the new slug:

```bash
beacon link-spec <NNN-slug> --epic <epic-slug>
```

This writes `specs/<NNN-slug>/.beacon.toml` (BEACON's spec→epic backlink, owned by BEACON — SpecKit ignores it) and adds the spec to the epic's `## Specs` section. `beacon doctor` will confirm with `spec-backlink-integrity: All N spec folder(s) backlink an epic.`

If you skip this step, `beacon doctor` will WARN until the user runs `beacon link-spec` manually — `/beacon.specify` exists so they don't have to.

## Step 5 — Validate the generated spec

Run the deterministic spec validator (same machine-truth checks as `/beacon.plan`, so results are reproducible across agents):

```bash
beacon spec validate <NNN-slug>    # defaults to the current spec branch if omitted
```

It scans `specs/<NNN-slug>/spec.md` for leftover `[NEEDS CLARIFICATION: …]` and other anchored template placeholders (`[REPLACE WITH ...]`, `<TBD>` / `<TODO>`, `[FEATURE NAME]` / `[DATE]` / `[###-feature-name]`), and resolves any `ADR-NNN` references against `project-management/ADRs/`. It exits non-zero and prints each hit with `file:line` context. A `[NEEDS CLARIFICATION:` marker means the spec still has an open question the user must resolve before `/beacon.plan`. Surface the output; a clean run is the bar.
