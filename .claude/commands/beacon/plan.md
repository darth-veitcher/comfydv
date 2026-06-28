---
description: Run SpecKit's plan command, then validate placeholders + ADR references in the generated plan.
argument-hint: (no arguments — operates on the current spec branch)
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

## SpecKit's plan skill (inlined verbatim)

@.claude/skills/speckit-plan/SKILL.md

## After plan.md is generated — BEACON post-checks

Run the deterministic validator (don't hand-roll a grep — the patterns drift and
unanchored ones false-positive on prose like "the TODO this spec retires"):

```bash
beacon plan validate <NNN-slug>    # defaults to the current spec branch if omitted
```

It performs two machine-truth checks over `specs/<NNN-slug>/plan.md`:

1. **Placeholder sweep.** Anchored template markers only — `[REPLACE WITH ...]` /
   `[REPLACE_WITH_*]`, `<TBD>` / `<TODO>`, `[NEEDS CLARIFICATION: …]`, and the
   template literals `[FEATURE NAME]` / `[DATE]` / `[###-feature-name]`. A bare word
   in running prose never matches.
2. **ADR existence.** Every `ADR-NNN` reference (bare or inside a Markdown link) is
   resolved against `project-management/ADRs/ADR-NNN-*.md` via `pathlib` — no shell
   glob, no quoting drift.

The command exits non-zero and prints each hit with `file:line` context. Surface that
output to the user. Non-blocking — the user decides whether to address before
`/beacon.tasks`, but a clean run is the bar.

If plan.md references a decision that should have been an epic-level ADR (i.e. a choice that constrains more than one spec) but isn't yet captured, note that too — the user may want to add the ADR to the parent epic's `## ADRs` section.
