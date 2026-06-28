---
description: Author or amend this project's Spec Kit constitution, seeded from BEACON's pragmatic principles and the project's own Background docs — so the plan gate has real rules to enforce, not placeholders.
argument-hint: [optional focus or extra principles]  — e.g. "emphasise accessibility and zero-downtime deploys"
allowed-tools: Bash, Read, Write, Edit, Glob
---

You're authoring (or amending) this project's **constitution** — the principles
Spec Kit's plan gate enforces. A fresh `specify init` leaves
`.specify/memory/constitution.md` full of placeholders (`[PRINCIPLE_1_NAME]`,
`RATIFICATION_DATE`, …); until they're replaced the gate has nothing to check.
This command fills it in, seeded from what BEACON already knows about the project.

The user's invocation (optional extra focus / principles):

$ARGUMENTS

## Step 1 — Gather BEACON seed material

The constitution should encode *this project's* non-negotiable principles, not
generic boilerplate. Pull from sources BEACON already ships and loads:

- **BEACON's principles**, already in the BEACON block of `.claude/CLAUDE.md`:
  the "Pragmatic design principles" table (DRY, Orthogonality, Reversibility,
  Simplicity, Broken Windows), the **Quality gates** for this project's language,
  and the bar — *"Would I proudly sign my name to this?"* These are strong default
  articles; carry the ones that fit into the constitution.
- **Project-specific context**: read
  `project-management/Background/00-problem-statement.md` and
  `project-management/Background/01-final-architecture-document.md`. The problem
  statement's constraints and the architecture's commitments are constitution
  material (e.g. "ships to PyPI via Trusted Publishing", "Python 3.11+",
  "offline-first"). If these still contain template placeholders, note that and
  prefer principles you can state confidently.
- Anything the user named in `$ARGUMENTS` above.

**Mind the seam — Constitution ≠ ADR.** `.specify/memory/constitution.md` holds
*enforceable principles* that the plan gate checks against; `project-management/ADRs/`
holds *specific decisions* with rationale. They coexist — don't copy ADR decisions
into the constitution; distil the principles those decisions express.

## Step 2 — Run Spec Kit's constitution command

Spec Kit's constitution skill is inlined verbatim below. Apply it, replacing every
placeholder with concrete text drawn from Step 1. Leave no bracketed
`[SCREAMING_SNAKE]` tokens and no bare `RATIFICATION_DATE` / `CONSTITUTION_VERSION`
sentinels behind (a slot you deliberately leave open should still say so explicitly,
not keep the template token).

@.claude/skills/speckit-constitution/SKILL.md

## Step 3 — Confirm

Confirm the constitution was written to `.specify/memory/constitution.md` and that
no template placeholders remain. Remind the user it now **gates `/beacon.plan`** —
`/speckit-plan`'s Constitution Check evaluates each plan against these articles.

`beacon doctor` will surface a `constitution` warning for as long as placeholder
tokens remain, so a clean fill clears it.
