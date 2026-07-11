# Implementation Plan: LLM Provider Abstraction

**Branch**: `007-llm-provider-abstraction` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-llm-provider-abstraction/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Define a shared `LLMProvider` protocol (list/load/unload/chat/structured-chat)
and generic ComfyUI nodes so workflow authors can connect any supported local
inference backend the same way. Migrate the existing Ollama integration onto
it — `OllamaProvider` becomes the first (and, in this feature, only)
implementation — including moving structured-output from ADR-006's
hand-rolled tool-calling onto `pydantic-ai`, per ADR-007. This is a
behavior-preserving mechanism swap for existing capability, plus the new
protocol boundary that the follow-on `llamacpp-integration` epic builds a
second provider against.

## Technical Context

**Language/Version**: Python ≥3.11 (per `pyproject.toml`)

**Primary Dependencies**: `aiohttp` (existing, unchanged — model-management
REST calls), `pydantic` (existing, unchanged — validation), `pydantic-ai` +
`openai` (new, per ADR-007 — powers `chat_structured()` only)

**Storage**: N/A — no persistent storage; the existing in-memory
`_TTLLRUCache` for model listing is reused unchanged inside `OllamaProvider`

**Testing**: `pytest` via `uv run pytest`, following `tests/test_ollama.py`'s
existing conventions (mocked `aiohttp`/`pydantic-ai` calls, no live server
required for unit tests; the existing `integration` pytest marker — "requiring
live Ollama at localhost:11434" — is reused for tests that exercise a real
server)

**Target Platform**: ComfyUI custom-node runtime, cross-platform wherever
ComfyUI runs; CPU-only dev harness per the project's stated vision

**Project Type**: Library / ComfyUI custom-node pack (single project,
existing `src/comfydv/` layout — no new top-level project)

**Performance Goals**: No new numeric target; must not add latency beyond the
existing bounded retry loop already in ADR-006 (`max_retries`, 0–5)

**Constraints**: Behavior-preserving for existing Ollama structured/
non-structured chat and all model-management calls (FR-007, FR-008); no new
dependency beyond what ADR-007 already accepted (`pydantic-ai`, `openai`,
their transitive `httpx`/`tiktoken`); model-management stays on `aiohttp`

**Scale/Scope**: One new internal package (`src/comfydv/_llm/`), migration of
the existing 1056-line `ollama.py` node/HTTP logic to consume it, five
ComfyUI node classes renamed to generic names — no change to the project's
single-repo, single-package scope

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Notes |
|---|---|---|
| I. ComfyUI Contract First | PASS | Generic nodes (`ChatCompletion`, `LLMModelSelector`, `LLMLoadModel`, `LLMUnloadModel`, `OllamaClient`) still expose `INPUT_TYPES`/`RETURN_TYPES`/`RETURN_NAMES`/`FUNCTION`/`CATEGORY`; `NODE_CLASS_MAPPINGS` in `__init__.py` remains the only install-time interface. `LLMProvider` is internal, not a ComfyUI-facing contract change beyond the node/socket rename. |
| II. Sandbox All User-Supplied Code | N/A | No template/expression evaluation in this feature — structured-output schemas are parsed as JSON Schema by `pydantic`, never `eval`/`exec`. |
| III. Test-First | PASS (binding on tasks/implement phases) | `tests/test_ollama.py`'s existing assertions are the regression oracle (see `research.md`); new `_llm` package gets tests written before implementation, red→green→refactor. |
| IV. Graceful Degradation Outside ComfyUI | PASS (binding on implementation) | `src/comfydv/_llm/` must not import `comfy`/`server` at module scope, matching `ollama.py`'s existing guarded-import pattern. |
| V. Simplicity — Function Before Class | **Justified exception — see Complexity Tracking** | `LLMProvider` is a `Protocol` implemented by stateful provider classes, not module-level functions. |
| VI. Fixed Output Positions | PASS (binding on implementation) | `ChatCompletion`'s (renamed from `OllamaChatCompletion`) `RETURN_TYPES`/`RETURN_NAMES` positions 0/1 carry forward unchanged — only the class/node name and internal mechanism change. |

Re-checked post-Phase 1 design (data-model.md, contracts/): unchanged — the
`Protocol`-based design in `contracts/llm_provider_protocol.md` is exactly
what was justified below, no new gate violations introduced by the detailed
design.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/comfydv/
├── ollama.py               # existing — node classes renamed to generic names,
│                            # delegates HTTP/chat logic to _llm/ internally
├── _llm/                   # new internal package (not a ComfyUI node module)
│   ├── __init__.py
│   ├── provider.py         # LLMProvider Protocol, ModelStatus, ModelInfo, Message
│   ├── ollama_provider.py  # OllamaProvider — wraps existing aiohttp REST logic
│   └── chat.py             # shared chat_structured() pydantic-ai helper
└── __init__.py              # NODE_CLASS_MAPPINGS updated for renamed nodes

tests/
├── test_ollama.py           # existing — updated for renamed nodes; behavior-
│                             # preserving assertions carried forward unchanged
└── test_llm_provider.py     # new — protocol conformance + OllamaProvider unit tests
```

**Structure Decision**: Single project (existing `src/comfydv/` layout, no new
top-level project). New internal package `src/comfydv/_llm/` (underscore
prefix marks it as internal, consistent with existing internal helpers like
`_TTLLRUCache` that already live inside `ollama.py`) hosts the protocol and
shared chat logic; `ollama.py` keeps the actual ComfyUI-registered node
classes and becomes a thin caller into `_llm`.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| `LLMProvider` as a `Protocol` implemented by stateful classes (Principle V: Function Before Class) | Every one of the five protocol methods (`list_models`/`load_model`/`unload_model`/`chat`/`chat_structured`) needs the same connection state (host, auth headers) — genuine shared state, the exact condition under which the constitution allows a class. A `Protocol` also lets ComfyUI's `LLM_CLIENT` socket carry one opaque object satisfying the shape, which is what makes the adapter pattern (ADR-007) work on the canvas. | Module-level functions taking host/headers as explicit parameters on every call were considered and rejected: they'd reintroduce the exact per-call-site repetition [ADR-005](../../project-management/ADRs/ADR-005-ollama-host-config-via-client-node.md)'s config-node pattern was built to eliminate, and a bare function can't be the typed payload of a ComfyUI socket the way an object implementing a `Protocol` can. |
