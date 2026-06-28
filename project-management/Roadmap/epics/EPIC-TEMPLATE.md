# Epic: <Title>

## Status
Planning  — started YYYY-MM-DD

## Why now
<Strategic context: why this epic this quarter, not next. One-to-three paragraphs.>

## Specs
_SpecKit specs that contribute to this epic. Linked automatically when
`beacon specify --epic <slug>` is used; otherwise add manually after running
`/speckit-specify`._

<!-- - specs/001-example/   — short description -->

## ADRs
_Cross-cutting decisions this epic required. **Creating or editing an epic is a
BEACON DESIGN-phase activity** — architectural choices that span specs
("OAuth vs own auth", "which database", "build vs buy", "where this sits on the
Wardley Map") belong here, not in any single spec.md. SpecKit's spec format
can't capture cross-spec decisions; epic-level ADRs are where they live._

_Create ADRs as `project-management/ADRs/ADR-NNN-name.md` (MADR format) and list
them below._

<!-- - project-management/ADRs/ADR-005-oauth-provider-choice.md -->
<!-- - project-management/ADRs/ADR-006-session-storage.md -->

## Success criteria
- <Outcome 1, measurable, attributable to this epic>
- <Outcome 2>
- <Outcome 3>

## Non-goals
<What this epic is explicitly NOT solving. Prevents scope creep when mid-flight
revelations tempt expansion.>

## Notes
<Cross-spec design notes, open questions, dependency tracking that doesn't
warrant a full ADR.>

---

*This template lives at `Roadmap/epics/EPIC-TEMPLATE.md`. `beacon epic new <slug>
--title "<Title>"` creates a new instance from it. Edit the body freely; the
structure of the headers is the contract `beacon` reads.*
