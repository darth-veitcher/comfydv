# Roadmap — Strategy

**Project:** comfydv  
**Last reviewed:** 2026-06-28

---

> This file is **strategy** (quarter-scope). It is **not** the live status tracker
> for active work — that's discovered from git branches and `specs/` by
> `beacon bullet list`. It is **not** the per-initiative artifact — those live as
> per-file epics under [`epics/`](./epics/).
>
> What goes here: vision, quarter priorities, sequencing, dependency notes, and
> the broader product context the in-flight epics ladder up to.

---

## Vision

`comfydv` is a small, high-quality ComfyUI utility pack that fills the gaps the core node library leaves: composable string formatting, seed-controlled randomisation, and workflow flow-control. Winning looks like: every node is well-tested, installs in one step, produces no surprises in production workflows, and is documented well enough that a non-programmer ComfyUI user can connect it without reading source code.

---

## This quarter (Q3 2026)

- **BEACON bootstrap** — `epics/archive/beacon-bootstrap.md` — ✅ DONE — BEACON framework wired up; problem statement, constitution, roadmap, and ADR template populated; quality gates clean
- **Logging modernisation** — `epics/logging-modernisation.md` — ✅ DONE — stdlib logging, NullHandler, silent-by-default; colorama/rich/termcolor removed; 11 tests
- **ComfyUI UX Polish & Manager Compatibility** — `epics/ux-and-install.md` — 🔄 ACTIVE — Fix installation, core UX bugs (debounce, connection drops, alert dialogs), correctness bugs (class-level mutation, IS_CHANGED, seed=0), and metadata drift
- **LLM Provider Abstraction** — `epics/archive/llm-provider-abstraction.md` — ✅ DONE — shared `LLMProvider` protocol (list/load/unload/chat/structured-output) and generic ComfyUI nodes; Ollama integration migrated onto it (ADR-007, supersedes ADR-006); merged via PR #17
- **llama.cpp Model Integration** — `epics/llamacpp-integration.md` — 🔄 ACTIVE — Add a `LlamaCppProvider` implementing the shared protocol via llama-server's router mode (GitHub issue #15); dependency on LLM Provider Abstraction now satisfied

For the live rollup (specs per epic, % tasks complete, last-commit age):

```
beacon epic list --detailed
```

---

## Sequencing and dependencies

- **BEACON bootstrap** is a prerequisite for all other epics (quality gates need to pass before new work merges)
- **Test hardening** is independent of documentation and can run in parallel
- **Documentation** depends on the final node API (output order, input names) being stable — start after test hardening locks the contracts
- **llama.cpp Model Integration** depends on **LLM Provider Abstraction** landing first — its `LlamaCppProvider` implements the protocol that epic defines, and reuses its generic nodes as-is

---

## Out of scope this quarter

- PyPI / ComfyUI Manager listing — deferred until test coverage is solid and the API is stable
- GPU-dependent nodes — out of scope; the utility pack is CPU-only by design
- Multi-language template engines (Handlebars, Liquid, etc.) — not planned; Jinja2 covers the use cases
- A UI node editor or visual template builder — too complex; out of scope for this stage

---

## Where things live

| Layer | Where | What's in it |
|---|---|---|
| Strategy | this file | vision, quarter priorities (slow, manual) |
| Epic / initiative | `epics/<slug>.md` | scope, ADRs, owned specs (weeks-scope) |
| Feature / spec | `specs/<NNN-slug>/` | SpecKit-generated user scenarios, plan, tasks |
| Active work | git branches + `specs/<NNN-slug>/tasks.md` + `.beacon/bullets.toml` | discovered live by `beacon bullet list` |
| Architectural decisions | `project-management/ADRs/` | epic-level MADRs, linked from the relevant epic |

---

*Last reviewed: 2026-06-28 — initial population. `beacon doctor` will warn if it goes stale (>90 days).*
