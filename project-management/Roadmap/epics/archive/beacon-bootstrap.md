# Epic: BEACON Bootstrap

## Status
Done — completed 2026-06-28

## Why now
No structured planning artefacts exist. Quality gates (`ruff`, `ty`, `beacon doctor`) are not yet enforced, and there is no problem statement, constitution, or roadmap to guide future work. This is the prerequisite for every other epic — nothing else should merge until the framework is clean.

## Dependencies
_None — this is the first epic._

## Specs
_None — bootstrap is a chore; no SpecKit spec needed._

## ADRs
_None required at this stage; architectural decisions will be captured as features are specified._

## Success criteria
- [x] `project-management/Background/00-problem-statement.md` filled in (no placeholder tokens)
- [x] `.specify/memory/constitution.md` authored with project-specific principles
- [x] `project-management/Roadmap/README.md` populated with vision and Q3 priorities
- [x] `project-management/Background/01-final-architecture-document.md` reflects actual system
- [ ] `beacon doctor --strict` exits 0 (no warnings, no failures)
- [ ] `README.md` has What-is-this, Install, and Quickstart sections
- [ ] `CHANGELOG.md` exists in Keep a Changelog format
- [ ] `pyproject.toml` has `repository` and `documentation` under `[project.urls]`

## Non-goals
- Not a feature epic — no user-facing code ships here
- Not an ADR audit — ADRs will be added as design decisions arise in future epics

## Notes
Bootstrap bullet registered on `feat/beacon`. All artefact writes land in a single PR to `develop`.
