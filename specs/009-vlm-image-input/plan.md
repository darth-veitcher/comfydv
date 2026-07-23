# Implementation Plan: VLM Image Input for ChatCompletion

**Branch**: `009-vlm-image-input` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-vlm-image-input/spec.md`

## Summary

Let a workflow author wire a ComfyUI `IMAGE` into the existing generic
`ChatCompletion` node so a vision-capable model can describe or reason about it,
on **either** backend. Per ADR-008 (extending ADR-007's adapter pattern to a
second input modality), images ride on an optional `Message.images` carrier and
each provider translates that carrier into its own wire shape: Ollama's flat
`/api/chat` `images` array (passes through untouched), llama.cpp's OpenAI
`image_url` content-parts, and — for structured output — pydantic-ai
`BinaryContent`, shared by both backends through `OpenAIChatModel`. The node
converts its `IMAGE` tensor to base64 PNG; everything below the node deals only
in base64 strings. Text-only behaviour is byte-for-byte unchanged when no image
is wired.

## Technical Context

**Language/Version**: Python ≥3.11 (unchanged, per `pyproject.toml`)

**Primary Dependencies**: existing only for runtime — `aiohttp` (Ollama/llama.cpp
REST), `pydantic-ai-slim[openai]>=2.9.0` (structured path; its `BinaryContent`
multimodal type was verified against the installed 2.9.0 source, see
`research.md`). **No new core runtime dependency.** `pillow` is added to the
**dev** group so the node's tensor→PNG encoder is unit-testable without a live
ComfyUI; at runtime Pillow/numpy are ComfyUI-provided (same stance the repo
already takes for torch).

**Storage**: N/A — no persistent storage; reuses the existing
`_CHAT_RESPONSE_CACHE` (an `images` value participates in the cache key
automatically).

**Testing**: `pytest` via `uv run pytest`, following the
`tests/test_ollama_provider.py` convention (mock at each provider's own
`_post_json` / `Agent.run` seam, no live server or ComfyUI required). Test-first
per Constitution III; the tensor-encode test uses a synthetic tensor + Pillow.

**Target Platform**: ComfyUI custom-node runtime, same as the existing LLM nodes.

**Project Type**: Library / ComfyUI custom-node pack (single project).

**Performance Goals**: No new numeric target; image encoding is a one-shot
per-execution PNG encode, negligible against inference latency.

**Constraints**: Text-only requests MUST stay byte-identical (FR-003/SC-004) —
providers omit an empty `images` key. `src/comfydv/_llm/` must not import
torch/numpy/Pillow (Constitution IV) — tensor handling stays in the node.
llama.cpp image support requires a server launched with `--mmproj` (deployment
prerequisite, surfaced as a clear error when absent, not configured by comfydv).

**Scale/Scope**: One new `Message` field; a per-provider mapping in each
`chat()` plus the shared `chat_structured()`; one optional node input + a
node-local encode helper. No new node classes, no new socket types, no protocol
method changes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Notes |
|---|---|---|
| I. ComfyUI Contract First | PASS | `ChatCompletion` keeps its `INPUT_TYPES`/`RETURN_TYPES`/`FUNCTION`/`CATEGORY`; only an optional input is added. No new registration, no ComfyUI changes. |
| II. Sandbox All User-Supplied Code | N/A | No template/expression evaluation in this feature. |
| III. Test-First | PASS (binding) | Test contracts T1–T6 (`contracts/image-input-contract.md`) written test-first, mirroring `test_ollama_provider.py`. Each runs without a live ComfyUI/backend. |
| IV. Graceful Degradation Outside ComfyUI | PASS (binding) | `_llm/` stays torch/numpy/Pillow-free — pure base64 carrier + mapping, unit-testable. Tensor→PNG lives in `ollama.py` (already `comfy`-guarded) with lazy Pillow/numpy import, so module import outside ComfyUI is unaffected. |
| V. Simplicity — Function Before Class | PASS | No new class. New logic is a `Message` field, two small per-provider transforms, one shared helper edit, and one module-level encode function. |
| VI. Fixed Output Positions | PASS | Outputs are untouched — only an optional **input** is added; `RETURN_TYPES`/`RETURN_NAMES` positions 0/1 and the structured extra-outputs contract are unchanged. |

Re-checked post-Phase 1 design (data-model.md, contracts/): unchanged — no new
gate violations. No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/009-vlm-image-input/
├── plan.md                      # This file
├── research.md                  # Phase 0 — wire shapes verified against installed deps
├── data-model.md                # Phase 1 — Message.images + per-provider mapping
├── quickstart.md                # Phase 1 — minimal describe-an-image workflow
├── contracts/
│   └── image-input-contract.md  # Phase 1 — behavioural + test contracts (T1–T6)
├── checklists/requirements.md   # Spec quality checklist (from /speckit-specify)
└── tasks.md                     # Phase 2 (/speckit-tasks) — not created here
```

### Source Code (repository root)

```text
src/comfydv/
├── ollama.py                    # MODIFIED — ChatCompletion: optional `image` input +
│                                #   node-local _encode_image_tensor() (lazy Pillow/numpy)
├── _llm/
│   ├── provider.py              # MODIFIED — Message gains `images: list[str] | None = None`
│   ├── ollama_provider.py       # MODIFIED — chat(): pass flat images through; omit empty key
│   ├── llamacpp_provider.py     # MODIFIED — chat(): map images → OpenAI image_url parts
│   └── chat.py                  # MODIFIED — chat_structured(): images → BinaryContent on prompt
└── __init__.py                  # unchanged — no new node class or mapping

tests/
├── test_provider.py (or test_ollama_provider.py) # T1 Message carrier + regression
├── test_ollama_provider.py       # MODIFIED — T2 Ollama image mapping + text regression
├── test_llamacpp_provider.py     # MODIFIED — T3 llama.cpp content-parts + text regression
├── test_llm_chat.py / chat tests # T4 chat_structured multimodal + regression
└── test_ollama.py                # MODIFIED — T5 encode helper, T6 node input contract

pyproject.toml                    # MODIFIED — add `pillow` to [dependency-groups].dev only
```

**Structure Decision**: Purely additive edits to the four existing `_llm`/node
files that ADR-007 established — no new module, because there is no new class or
node (contrast 008, which added a provider + node). The image path threads
through the exact seams the text path already uses, which is the whole point of
ADR-008: a second modality on the same adapter, not a parallel structure.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

None — see Constitution Check above.
