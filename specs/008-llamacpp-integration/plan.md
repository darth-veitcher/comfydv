# Implementation Plan: llama.cpp Model Integration

**Branch**: `008-llamacpp-integration` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-llamacpp-integration/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Implement `LlamaCppProvider` as the second `LLMProvider` (ADR-007), backed by
`llama-server`'s router mode (`GET /models`, `POST /models/load`,
`POST /models/unload`, `/v1/chat/completions`). Add one new ComfyUI node
(`LlamaCppClient`) emitting the existing `LLM_CLIENT` socket type — no other
node classes change. This is the concrete proof the provider abstraction
(prerequisite epic, PR #17) actually generalizes: a second backend, zero
changes to `ChatCompletion`/`LLMModelSelector`/`LLMLoadModel`/`LLMUnloadModel`.

## Technical Context

**Language/Version**: Python ≥3.11 (unchanged, per `pyproject.toml`)

**Primary Dependencies**: `aiohttp` (existing — model-management REST calls),
`pydantic-ai`/`openai` (existing, from the prerequisite epic — `chat_structured()`
reuses the shared helper unchanged, zero new structured-output code)

**Storage**: N/A — no persistent storage; reuses the existing
`_MODEL_LIST_CACHE`/`_CHAT_RESPONSE_CACHE` infra pattern from `OllamaProvider`

**Testing**: `pytest` via `uv run pytest`, following `tests/test_ollama_provider.py`'s
established convention (mock at the provider's own `_post_json`/`_get_json`
seam, no live server required for unit tests)

**Target Platform**: ComfyUI custom-node runtime, same as the existing Ollama
integration

**Project Type**: Library / ComfyUI custom-node pack (single project, adds to
existing `src/comfydv/` layout)

**Performance Goals**: No new numeric target; must not add latency beyond
what `OllamaProvider`'s equivalent methods already accept

**Constraints**: Router-mode-only (spec.md Assumptions — a `llama-server`
without `--models-dir`/`--models-preset` doesn't expose these endpoints at
all, FR-006); model identifier field is `id` (llama.cpp) vs `name` (Ollama) —
`LlamaCppProvider.list_models()` must map this correctly (see `research.md`);
`status` is a nested object (`{"value": "..."}`), not a flat string

**Scale/Scope**: One new class (`LlamaCppProvider`, mirrors `OllamaProvider`'s
shape), one new ComfyUI node (`LlamaCppClient`), one new test file — no
changes to `ollama.py`, `_llm/provider.py`, `_llm/chat.py`, or any existing
node class

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Notes |
|---|---|---|
| I. ComfyUI Contract First | PASS | `LlamaCppClient` exposes the standard `INPUT_TYPES`/`RETURN_TYPES`/`FUNCTION`/`CATEGORY`; registered in `NODE_CLASS_MAPPINGS` like every other node. |
| II. Sandbox All User-Supplied Code | N/A | No template/expression evaluation in this feature. |
| III. Test-First | PASS (binding) | `tests/test_llamacpp_provider.py` written test-first, mirroring `test_ollama_provider.py`'s TDD-pair structure. |
| IV. Graceful Degradation Outside ComfyUI | PASS (binding) | `LlamaCppProvider` lives in `src/comfydv/_llm/`, which already has no `comfy`/`server` imports at module scope (verified for the prerequisite epic; this feature adds no new module-scope imports of either). |
| V. Simplicity — Function Before Class | PASS, same justification as `OllamaProvider` | `LlamaCppProvider` carries connection state (host, headers) across 5 methods — the same shared-state condition that already justified `OllamaProvider` as a class (research.md, prerequisite epic). No new gate — same precedent applies. |
| VI. Fixed Output Positions | N/A | `LlamaCppClient`'s single output (`client`) isn't a multi-output node; no positional contract to preserve. |

Re-checked post-Phase 1 design (data-model.md): unchanged — no new gate
violations. No Complexity Tracking entries needed (unlike the prerequisite
epic, this feature introduces no new pattern, just a second instance of an
already-justified one).

## Project Structure

### Documentation (this feature)

```text
specs/008-llamacpp-integration/
├── plan.md              # This file
├── research.md           # Phase 0 — router-mode API shape, verified live
├── data-model.md         # Phase 1 — LlamaCppProvider field mapping
├── quickstart.md         # Phase 1 — minimal workflow walkthrough
├── contracts/            # Phase 1 — LlamaCppProvider's protocol conformance
└── tasks.md              # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/comfydv/
├── ollama.py                    # unchanged — add LlamaCppClient node only via a new module
├── llamacpp.py                  # new — LlamaCppClient node (mirrors OllamaClient's shape)
├── _llm/
│   ├── provider.py              # unchanged — LLMProvider/ModelStatus/ModelInfo/Message
│   ├── ollama_provider.py       # unchanged
│   ├── llamacpp_provider.py     # new — LlamaCppProvider (mirrors ollama_provider.py's shape)
│   └── chat.py                  # unchanged — chat_structured() reused as-is
└── __init__.py                  # add LlamaCppClient import + NODE_CLASS_MAPPINGS entry

tests/
├── test_ollama_provider.py       # unchanged
├── test_llamacpp_provider.py     # new — mirrors test_ollama_provider.py's structure
└── test_llamacpp.py              # new — LlamaCppClient node contract test (small; mirrors
                                   #        the OllamaClient-specific slice of test_ollama.py)
```

**Structure Decision**: New `src/comfydv/llamacpp.py` module (not added into
`ollama.py`) for the `LlamaCppClient` node, and a new `src/comfydv/_llm/llamacpp_provider.py`
for `LlamaCppProvider` — mirroring the existing `ollama.py`/`ollama_provider.py`
split exactly, so the two backends read as parallel, symmetric implementations
rather than one growing to accommodate the other. No existing file is
modified except `__init__.py`'s registration block.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

None — see Constitution Check above.
