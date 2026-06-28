---
name: beacon-design
description: BEACON DESIGN phase — make architecture decisions and decompose work into daily-shippable tracer bullets. Pairs with Spec Kit's spec workflow. Use when the user says "How should I architect…", "Design this feature", or "Break this down into bullets".
---

# Phase 2: DESIGN — Architecture and tracer bullet decomposition

**Purpose:** Make key decisions, document them as ADRs, and break work into daily-shippable tracer bullets.

**Entry triggers:** "How should I architect…" / "Design this feature" / "Break this down into bullets" / "Plan this initiative" / "New quarter, what are we building" *(epic-level)*

**DESIGN happens at two scales:**

1. **Epic-level** — cross-spec architectural decisions for a weeks-scope initiative.
   These span multiple SpecKit specs ("OAuth vs own auth", "which database", "build vs buy",
   "where is this on the Wardley Map") and so cannot live in any single `spec.md`.
   **Creating or editing an epic IS a DESIGN-phase activity.** Produce ADRs in
   `project-management/ADRs/` and link them in the epic's `## ADRs` section.
   This is the gap BEACON fills that SpecKit alone cannot.

2. **Spec-level** — feature-scoped scenarios + plan + tasks. SpecKit owns this:
   `/speckit-specify` → `/speckit-plan` → `/speckit-tasks`.

When in doubt: **if the decision affects more than one spec, it's epic-level**.

**Tools:**
- **Spec Kit** — the spec workflow: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` — the primary DESIGN output
- `/design:wardley <topic>` — Wardley Map for strategic landscape analysis; run **before** `/speckit-specify` when a build-vs-buy decision is involved
- `/design:evaluate <component>` — scored technology evaluation (build/OSS/SaaS); run when the design surfaces a significant technology choice

---

## DESIGN at the epic level (do this FIRST for new initiatives)

If this work is the start of a new initiative (not just a feature within an existing epic):

1. **Create the epic:** `beacon epic new <slug> --title "<Title>"`.
2. **Fill in the body** — vision, why-now, success criteria, non-goals. Three paragraphs of work; do it properly.
3. **Surface cross-spec decisions and write ADRs** — for each significant architectural choice that affects more than one spec:
   - `/design:wardley <topic>` if the build-vs-buy question is open
   - `/design:evaluate <component>` for scored technology comparison
   - Write the decision as `project-management/ADRs/ADR-NNN-name.md` (MADR format)
   - Link the ADR from the epic's `## ADRs` section
4. **Decompose the intended scope into stubs** — for each work-area the epic's
   Success criteria imply but you're not building yet, create a placeholder
   spec: `beacon epic stub <slug> "<title>" ["<title>" …]`. A stub blocks
   `beacon epic finish` until it's filled in, so the epic can't be archived with
   scope still on paper.
5. **Audit the decomposition** — run `/beacon.audit <slug>`. The read-only
   `beacon-auditor` subagent checks every Success criterion has an owning
   spec/stub and reports the gaps (with ready-to-run `beacon epic stub` lines).
   `Status: clear` means the epic is fully broken out and ready to build. This
   is a default-on *design* moment — the `auto-audit` hook also nudges you here
   right after `beacon epic stub`.
6. **Only then** start the first spec with `/speckit-specify` (or `beacon specify --epic <slug>` when the wrapper ships).

An epic with no ADRs after it's been Active for a while is a smell — it means
the cross-spec decisions were either trivial (rare) or skipped (more common,
more dangerous). `beacon doctor` will WARN.

## What DESIGN produces

### 1. Spec (via Spec Kit)

Run `/speckit-specify` → `/speckit-plan` → `/speckit-tasks`. This produces three
files in `specs/[feature-name]/`:

- **`spec.md`** — user scenarios and acceptance criteria; each is directly testable
- **`plan.md`** — architecture, components, data models, and diagrams:
  - Sequence (happy path + errors, `autonumber`)
  - ERD (when data entities are introduced/changed)
  - Component diagram (when ≥3 internal components)
  - State diagram (when an entity lifecycle is involved)
- **`tasks.md`** — tracer bullet breakdown

Optionally run `/speckit-clarify` before `/speckit-plan` to de-risk ambiguity,
and `/speckit-analyze` after `/speckit-tasks` to check cross-artifact consistency.

Use `/design:diagram <component>` to generate or regenerate any diagram.

### 2. Architecture document

Update `project-management/Background/01-final-architecture-document.md` if the design changes the overall system architecture.

### 3. ADRs

For every decision that is hard to reverse or involves a real tradeoff, create an ADR in `project-management/ADRs/` using MADR format (see `ADR-000-template.md`).

---

## Tracer bullet rules

Each task in `tasks.md` must be a tracer bullet:

| Rule | Why |
|------|-----|
| Vertical slice — touches all layers | Proves plumbing works end-to-end |
| Takes 2–4 hours maximum | Forces scope discipline; split if larger |
| User-visible output | Can be demoed; progress is tangible |
| Previous bullets still pass | No regressions |
| Could deploy as-is (even if limited) | Maintains "always deployable" invariant |

**Anti-pattern:** planning entire layers separately (all database first, then all API, then all UI). This produces nothing shippable until day N.

---

## Design checklist

Before leaving DESIGN:

- [ ] Strategic landscape checked — if a build-vs-buy decision exists, `/design:wardley` run and saved to `Work/analysis/`
- [ ] Technology choices evaluated — if a significant technology was selected, `/design:evaluate` run and ADR created
- [ ] Epic decomposition audited — `/beacon.audit <slug>` returns `Status: clear` (every Success criterion has an owning spec/stub)
- [ ] `spec.md` complete — user scenarios and testable acceptance criteria
- [ ] `plan.md` complete — actual file paths, component names, data models, and diagrams:
  - [ ] Sequence (happy path with `autonumber`)
  - [ ] Sequence (error/alternative paths)
  - [ ] ERD (if data entities introduced/changed)
  - [ ] Component diagram (if ≥3 internal components)
  - [ ] State diagram (if entity lifecycle involved)
- [ ] `tasks.md` complete — bullets sequenced, each ≤4h
- [ ] ADRs written for all major decisions
- [ ] `01-final-architecture-document.md` updated if architecture changed
- [ ] `project-management/Roadmap/README.md` updated with new bullets

**Do not start BUILD until `spec.md`, `plan.md`, and `tasks.md` are complete.**
