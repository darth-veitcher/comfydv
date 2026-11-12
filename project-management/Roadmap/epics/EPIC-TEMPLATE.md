# Epic: <Title>

<!-- Write this epic to section 7 of docs/WRITING.md (ASD-STE100). -->

## Status
Planning  — started YYYY-MM-DD

## Why now
<Strategic context: why this epic this quarter, not next. One to three paragraphs.>

## Specs
_SpecKit specs that contribute to this epic. `beacon specify --epic <slug>`
links them. Otherwise, add each one by hand after you run `/speckit-specify`._

<!-- - specs/001-example/   — short description -->

## ADRs
_Decisions that cross the specs of this epic. **To create or edit an epic is a
BEACON DESIGN-phase activity.** An architectural choice that spans specs belongs
here, not in one spec.md. Examples: "OAuth or our own auth", "which database",
"build or buy", "where this sits on the Wardley Map". The SpecKit spec format
cannot record a decision that crosses specs, so the epic-level ADRs record it._

_Write each ADR as `project-management/ADRs/ADR-NNN-name.md` (MADR format). List
it below as a path, a Markdown link, or a bullet that starts with `ADR-NNN`. Until
the ADR exists, write the decision as a sentence. `beacon doctor` reads a bullet
that is a sentence as a pending decision, not as a broken link._

<!-- - project-management/ADRs/ADR-005-oauth-provider-choice.md -->
<!-- - project-management/ADRs/ADR-006-session-storage.md -->

## Success criteria
- <Outcome 1, measurable, attributable to this epic>
- <Outcome 2>
- <Outcome 3>

## Non-goals
<What this epic explicitly does not solve. This list stops scope creep when new
ideas occur during the work.>

## Notes
<Cross-spec design notes, open questions, and dependency notes that do not need a
full ADR.>

---

*This template is at `Roadmap/epics/EPIC-TEMPLATE.md`. `beacon epic new <slug>
--title "<Title>"` makes a new epic from it. Edit the body as necessary. `beacon`
reads the structure of the headers, so keep them.*
