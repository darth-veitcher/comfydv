---
description: Bidirectional PRD bridge — export a PRD from a BEACON epic, or import an existing PRD to scaffold the epic, problem statement, and ADR stubs.
argument-hint: <epic-slug>  — export  |  import <path>  — ingest an existing PRD
allowed-tools: Bash, Read, Write, Edit
---

You're operating the BEACON ↔ PRD bridge. The user's invocation:

$ARGUMENTS

## Step 1 — Determine mode

- If the first token of `$ARGUMENTS` is **`import`**, the rest is a file path: go to **[Import mode](#import-mode)**.
- Otherwise, treat the entire argument as an **epic slug**: go to **[Export mode](#export-mode)**.

---

## Export mode

Generate a PRD markdown file from an existing BEACON epic.

### Step E1 — Load the epic

Read `project-management/Roadmap/epics/<slug>.md`. If it doesn't exist, STOP:

```
No epic found at project-management/Roadmap/epics/<slug>.md.
Create it first: beacon epic new <slug> --title "<title>"
```

Extract from the epic file:
- **Title** (from `# Epic: <Title>`)
- **Status** (from `## Status` line)
- **Why now** (full `## Why now` body)
- **Success criteria** (bullet list under `## Success criteria`)
- **Non-goals** (body under `## Non-goals`)
- **Spec paths** (bullet list under `## Specs`)
- **ADR paths** (bullet list under `## ADRs`)
- **Notes** (body under `## Notes`, if present)

### Step E2 — Load supporting artefacts

1. **Problem statement** — read `project-management/Background/00-problem-statement.md`. If absent, skip gracefully (leave the PRD section blank with a note).
2. **ADR files** — for each path listed in the epic's `## ADRs`, read the file and extract its title, status, and the one-sentence decision under `## Decision`.
3. **Spec rollup** — run:
   ```bash
   beacon epic list --detailed
   ```
   Find this epic's row and note shipped / in-flight / missing counts.

### Step E3 — Check for a custom template

Check whether `.beacon/prd-template.md` exists:
```bash
test -f project-management/.beacon/prd-template.md && echo found
```
If found, read it and use its section structure (preserving any `{{PLACEHOLDER}}` instructions in it as prompts to yourself). Otherwise use the default structure below.

### Step E4 — Write the PRD

Write `project-management/Roadmap/epics/<slug>-prd.md` with this structure (default, no custom template):

```markdown
# PRD: <Epic Title>

**Status:** <epic status> | **Epic:** `epics/<slug>.md` | **Generated:** <today's date>

---

## Executive Summary

<2–3 sentences: why this initiative exists now, what success looks like, and how it fits the current quarter's strategy. Synthesise from "Why now" + success criteria.>

## Problem Statement

<Synthesised from 00-problem-statement.md: core problem, target user, current pain, constraints. If the file was absent, note: "Problem statement not yet authored — run beacon seed.">

## Goals

<Success criteria from the epic, formatted as measurable outcomes.>

## Non-Goals

<Non-goals from the epic verbatim.>

## Scope & Delivery

| Spec | State |
|---|---|
<One row per spec path. State = Shipped / In flight / Planned (from rollup). If no specs listed, note "No specs created yet.">

## Key Decisions

<One subsection per ADR:>
### <ADR title>
**Status:** <ADR status> | **File:** `<ADR path>`
<One-sentence summary of the decision.>

## Success Metrics

<Restate the epic's success criteria as testable, measurable outcomes — add any quantitative framing that can be inferred from the problem statement.>

## Open Questions

<Notes section from the epic, if present. If empty or absent, omit this section.>
```

### Step E5 — Report

Print:
```
PRD written → project-management/Roadmap/epics/<slug>-prd.md
```

---

## Import mode

Ingest an existing PRD and scaffold the BEACON artefacts from it.

### Step I1 — Read the PRD

Read the file at the path given after `import`. If it doesn't exist, STOP with a clear error.

### Step I2 — Extract structured content

From the PRD, identify and extract (best-effort — PRD formats vary):

| PRD concept | Maps to |
|---|---|
| Document title / product name | Epic title → derive kebab-case slug |
| Problem / background / executive summary | `00-problem-statement.md` — core problem + target user |
| Goals / success criteria | Epic `## Success criteria` |
| Non-goals / out of scope | Epic `## Non-goals` |
| Strategic context / why now / motivation | Epic `## Why now` |
| Features / requirements / scope items | Suggested spec slugs (list only — do not create) |
| Architecture / technical decisions | ADR stubs |
| Constraints / timeline | Epic `## Notes` |

Derive a kebab-case **epic slug** from the title (e.g. "User Authentication v2" → `user-authentication-v2`).

### Step I3 — Check for collisions

Before writing anything:
- Does `project-management/Roadmap/epics/<slug>.md` already exist? If yes, STOP and tell the user:
  ```
  Epic <slug> already exists. Choose a different slug or edit the epic manually.
  ```
- Does `project-management/Background/00-problem-statement.md` exist and contain non-placeholder content? If yes, do NOT overwrite — instead append an `## Imported from PRD` section at the bottom and note the merge to the user.

### Step I4 — Scaffold BEACON artefacts

**1. Problem statement**

Write (or append to) `project-management/Background/00-problem-statement.md` with the extracted problem, target user, success criteria, and constraints.

**2. Epic**

```bash
beacon epic new <slug> --title "<Title>"
```

Then open `project-management/Roadmap/epics/<slug>.md` and fill in:
- `## Why now` — from the PRD's strategic context
- `## Success criteria` — from the PRD's goals
- `## Non-goals` — from the PRD's out-of-scope section
- `## Notes` — constraints, timeline notes, any open questions from the PRD

**3. ADR stubs** (one per identifiable technical decision in the PRD)

Find the next available ADR number:
```bash
ls project-management/ADRs/ADR-*.md 2>/dev/null | sort | tail -1
```

For each decision, write `project-management/ADRs/ADR-NNN-<decision-slug>.md` using the MADR template. Set `Status: Proposed`. Populate `## Context` from the PRD text; leave `## Decision` and `## Consequences` as prompts for the team to complete.

Add each ADR path to the epic's `## ADRs` section.

### Step I5 — Report

Print a structured summary:

```
BEACON artefacts scaffolded from PRD:

  ✓  project-management/Background/00-problem-statement.md  (written|appended)
  ✓  project-management/Roadmap/epics/<slug>.md
  ✓  project-management/ADRs/ADR-NNN-<slug>.md  (N stub(s))

Suggested specs — run /beacon.specify <slug> <feature> for each:
  • <feature 1 from PRD scope>
  • <feature 2>
  …

Next step: /beacon.specify <epic-slug> "<first feature>"
```
