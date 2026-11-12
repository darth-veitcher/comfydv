# Roadmap — Strategy

**Project:** comfydv  
**Last reviewed:** 2026-11-12

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

`comfydv` is a small, high-quality ComfyUI node pack. It has two parts:

- **Utility nodes**: string formatting, seed-controlled random choice and a
  circuit breaker.
- **Local LLM nodes**: chat, vision and (next) agents with tools, skills and a
  sandbox, on Ollama or llama.cpp.

Success means: each node has tests, installs in one step and causes no surprises in
production workflows. Its documentation is clear to a ComfyUI user without programming knowledge. Users get changes only as versioned releases.

---

## This quarter (Q4 2026)

Do the epics in this order. Each epic ships through the one before it.

1. **Release Pipeline & Distribution** — `epics/release-pipeline.md` — 📋 PLANNING —
   CI gate, `develop` to PyPI pre-releases, `main` to PyPI and the Comfy Registry.
   This is first because comfydv has no releases: each merge to `main` goes to
   all users at once.
2. **LLM Node Naming (clean break)** — `epics/llm-node-naming.md` — 📋 PLANNING —
   Remove "Ollama" from the names of nodes that operate with both backends.
   It ships as the first release with a documented breaking change.
3. **LLM Agent Harness** — `epics/llm-agent-harness.md` — 📋 PLANNING — Agent
   node with MCP tools, skills and a Monty sandbox (ADR-011 to ADR-014).
4. **ComfyUI UX Polish** — `epics/ux-and-install.md` — ⏸ PAUSED — The FormatString
   and RandomChoice bugs in specs 003 and 004. It resumes after the release pipeline.

Done this quarter:

- **llama.cpp Model Integration** — `epics/archive/llamacpp-integration.md` — ✅ DONE
- **VLM Image Input for ChatCompletion** — `epics/archive/vlm-image-input.md` — ✅ DONE.
  One follow-up is open: a test against a live vision backend (spec 009, T010).
- **Agent harness design and dependency upgrade** — PR #37 — pydantic-ai 2.68, MCP,
  Monty, telemetry off by default, BEACON 1.18 and Spec Kit 1.0.

Earlier quarters: `epics/archive/` (BEACON bootstrap, logging, Ollama integration,
LLM provider abstraction).

For the live rollup (specs per epic, % tasks complete, last-commit age):

```
beacon epic list --detailed
```

---

## Sequencing and dependencies

- **Release pipeline** comes before all user-visible changes. It needs the CI gate
  to start green, so this quarter's lint and type cleanup is a prerequisite (done in PR #37).
- **Node naming** depends on the release pipeline. A clean break is acceptable only
  in a versioned release with migration notes.
- **Agent harness** depends on node naming, so that its new nodes start with their
  final names. It uses the dependency upgrade in PR #37.
- **UX polish** is independent of the LLM epics. It can run in parallel when the
  release pipeline is ready.

---

## Out of scope this quarter

- A `1.0.0` release. Decide after the agent harness ships.
- Cloud LLM providers (OpenAI, Anthropic) as LLM clients.
- GPU-dependent utility nodes.
- Template engines other than Jinja2 and Python f-strings.
- A visual template builder.

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

*Last reviewed: 2026-11-12 — Q4 strategy review: release pipeline first, then node naming, then the agent harness. `beacon doctor` warns if this file goes stale (>90 days).*
