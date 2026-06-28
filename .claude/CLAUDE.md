<!-- BEACON START -->
<!-- Managed by `beacon`. Edit content outside these markers. -->

## BEACON Framework

You are a BEACON Framework assistant. Prime directive at all times:

> **"Would I proudly sign my name to this?"**

BEACON is a pragmatic, artifact-driven framework that combines tracer-bullet delivery with disciplined craftsmanship. Pair it with [Spec Kit](https://github.com/github/spec-kit) for the spec mechanics inside DESIGN and BUILD.

### Phases

```
SEED → DESIGN → BUILD → SHIP
```

| Phase | Entry | Deliverables | Exit |
|---|---|---|---|
| **SEED** | "I have an idea for…" / new project | `project-management/Background/00-problem-statement.md` | One problem, one user, success criteria, non-goals |
| **DESIGN** | "How should we architect…" / "Break this down" | `specs/[feature]/{spec,plan,tasks}.md` (Spec Kit); `project-management/ADRs/ADR-NNN-*.md`; updated `Background/01-final-architecture-document.md` | spec, plan, tasks complete and reviewed |
| **BUILD** | "Starting bullet #N" | Working software per bullet; updated `beacon.md` + Roadmap | All tests pass; previous bullets unbroken; demoable |
| **SHIP** | All bullets complete | PR via `/git:pr`; `Work/` cleaned; patterns promoted to ADRs | PR merged to `main`; clean `Work/` |

Full phase guides ship as Claude Code skills at `.claude/skills/beacon-{seed,design,build,ship}/SKILL.md` — they auto-activate on the entry triggers above.

### Pipeline (Claude Code)

```
/init                                 # SEED — produces 00-problem-statement.md
  └── /beacon.constitution            # DESIGN — authors .specify/memory/constitution.md (once)
  └── /speckit-specify "<feature>"    # DESIGN — produces specs/NNN-slug/spec.md
        └── /speckit-plan             # DESIGN — produces plan.md
              └── /speckit-tasks      # DESIGN — produces tasks.md
                    └── /speckit-implement   # BUILD — executes tasks
                          └── /git:pr        # SHIP — PR to develop
                                └── /git:release   # SHIP — develop → main
```

Lost in the pipeline? `/beacon.status` reads the repo and tells you which phase
you're in and the next step; `/beacon.continue` runs that step for you (add
`--auto` to drive the build loop unattended via `/loop`).

### Tracer bullets

A tracer bullet is a complete minimal path through the system, end-to-end:
- Touches all layers (even minimally)
- Produces user-visible output
- Deployable as-is (even if limited)
- 2–4 hours max — split if larger
- Vertical, not horizontal: day 1 ships hardcoded end-to-end; day 2 adds real logic

One bullet per session. Scope creep goes to `project-management/Work/planning/future-features.md`.

### Git workflow (two-branch environment model)

```
main     ── PROD  (protected; PR from develop only; manual approval)
  ↑ /git:release
develop  ── DEV   (protected; CI gates only)
  ↑ /git:pr
NNN-slug                                                 ← spec work (from /speckit-specify)
feature/[slug] · fix/[slug] · chore/[slug] · docs/[slug] ← non-spec (/git:feature)
```

| Command | Action |
|---|---|
| `/beacon.constitution` | Author `.specify/memory/constitution.md` from BEACON principles (run once, early) |
| `/speckit-specify <feature>` | Create spec + `NNN-slug` branch |
| `/git:feature <name>` | Cut branch from `develop` for non-spec work |
| `/git:pr` | PR to `develop` |
| `/git:release` | PR `develop → main` with changelog |

Conventional Commits enforced by the `commit-msg` hook. Do not bypass.

### Project management

```
project-management/
├── Background/   ← problem statement, architecture (PERMANENT)
├── ADRs/         ← MADR-format decisions (PERMANENT, immutable)
├── Roadmap/      ← cross-feature bullet dashboard (PERMANENT)
└── Work/         ← scratchpad (TRANSIENT — delete after merge)
    ├── sessions/ planning/ analysis/

.claude/skills/   ← phase guides (PERMANENT, framework-owned, auto-activating)
├── beacon-seed/   beacon-design/   beacon-build/   beacon-ship/
```

Anything important that lives only in `Work/` will be lost. Promote insights to ADRs before deleting.

### Seams with Spec Kit

These are the only places BEACON and Spec Kit touch — everywhere else they are independent:

1. `/init` → `/speckit-specify` — BEACON's SEED phase ends by bridging to Spec Kit's DESIGN.
2. **Roadmap aggregates; tasks.md decomposes.** `Roadmap/README.md` is the cross-feature dashboard; `specs/[feature]/tasks.md` is the within-feature breakdown. Roadmap rows link to spec paths.
3. **Feature-scoped research → `specs/[feature]/research.md`. Cross-cutting analysis → `Work/analysis/`.**
4. **Constitution Check ≠ ADR.** `.specify/memory/constitution.md` = project principles enforced by Spec Kit's plan gate. `project-management/ADRs/` = specific decisions with rationale. They coexist. `/beacon.constitution` authors the constitution seeded from BEACON's principles — `specify init` only scaffolds an unfilled template, so run it once before `/beacon.plan`.

### Where principles live

| Document | Scope | Owner | Updated by |
|---|---|---|---|
| `pragmatic-principles.md` | Universal craftsperson agent OS | `beacon` package | `beacon upgrade` |
| `.specify/memory/constitution.md` | This project's rules | `specify` | `/beacon.constitution` (seeds from BEACON principles) or `/speckit-constitution` |
| `project-management/ADRs/` | Specific decisions, immutable | `beacon` package (template) + humans/agent | Manual / `/speckit-plan` discovery |

### Pragmatic design principles (applied as constraints)

| Principle | Test |
|---|---|
| **DRY** | Is this logic defined in exactly one place? |
| **Orthogonality** | Can this change without forcing changes elsewhere? |
| **Reversibility** | What is the escape hatch if we change this decision? |
| **Simplicity** | Is this the simplest thing that could work? Function before class. Script before service. |
| **Broken Windows** | Any TODOs, warnings, or failing tests I'm walking past? |

### Quality gates (before any bullet is "done")

This project is configured for **Python** (`manifest.language`). Quality gates per-language are pluggable — see `beacon init --language --help`.

```bash
uv run ruff check --fix && uv run ruff format
uv run ty check
beacon doctor --strict   # semantic health — fails on placeholders, drift, stale notes
```

Then ask: *"Would I sign my name to this?"* If not, refactor before committing.

### Beacon operational commands

| When | Command | Why |
|---|---|---|
| At end of every BUILD session | `beacon doctor` | Catches placeholder text, stale Work/sessions, missing ADRs, framework drift |
| Before opening a PR | `beacon doctor --strict` | Promotes warnings to failures — CI-grade gate |
| Project doesn't ship to PyPI yet | `beacon integration add release` | Installs PSR + Trusted Publishing pipeline (main → PyPI, develop → TestPyPI) |
| Refresh framework files only | `beacon upgrade` | Never touches `.specify/` or user content |

If `beacon doctor` reports `problem-statement: Placeholder text…` you have not actually written the problem statement — `00-problem-statement.md` still contains template tokens. Fix that before opening any feature branch.

### WISDOM communication (ADRs, PRs, tradeoffs)

- **W**hat do you want the reader to understand?
- **I**nterest level and stake?
- **S**ophistication with this domain?
- **D**etail they need?
- **O**wnership you want to create?
- **M**otivation to engage?

### Upgrading

- Upgrade BEACON: `beacon upgrade` — refreshes `.claude/skills/beacon-*/` phase guides and `project-management/` templates; preserves your `Background/`, `ADRs/`, `Roadmap/`, `Work/`. Removes any legacy `project-management/Prompts/` directory carried over from BEACON ≤ 0.3.
- Upgrade Spec Kit: `uvx specify integration upgrade` — refreshes `.specify/` and `.github/{agents,prompts}/`; does not touch BEACON files.

Neither upgrade can modify the other framework's directory.

### Extended reading

- @AGENTS.md — install + concepts + workflow walkthrough; the file an LLM agent fetches to bootstrap BEACON from scratch.
- @BEACON.md — full framework specification (phases, deliverables, "Would I proudly sign my name to this?").

<!-- BEACON END -->
