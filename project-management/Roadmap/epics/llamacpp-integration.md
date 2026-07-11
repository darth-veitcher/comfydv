# Epic: llama.cpp Model Integration

## Status
Active — started 2026-07-11

## Why now

GitHub issue #15 requests llama.cpp support "similar to Ollama." This is now
practical because llama.cpp's `llama-server` gained a "router mode" via
[llama.cpp PR #18228](https://github.com/ggml-org/llama.cpp/pull/18228)
(merged 2025-12-21): launched with `--models-dir <dir>` (or
`--models-preset <file>.ini`) instead of `-m`, it exposes `GET /models`
(with live status: `unloaded`/`loading`/`loaded`/`sleeping`/`downloading`),
`POST /models/load`, `POST /models/unload`, and `--sleep-idle-seconds`
auto-unload — giving llama.cpp the same manual load/unload
memory-management primitives comfydv already relies on for Ollama. With the
`llm-provider-abstraction` epic in place, adding llama.cpp is now a matter
of implementing one more `LLMProvider`, not building a parallel set of
ComfyUI nodes.

## Dependencies

Depended on the `llm-provider-abstraction` epic landing first — **satisfied**
2026-07-11, merged via [PR #17](https://github.com/darth-veitcher/comfydv/pull/17)
(`project-management/Roadmap/epics/archive/llm-provider-abstraction.md`).
This epic's `LlamaCppProvider` implements the `LLMProvider` protocol that
epic defined, and its `LlamaCppClient` node emits the same `LLM_CLIENT`
socket type the generic `ChatCompletion`/`LLMModelSelector`/`LLMLoadModel`/
`LLMUnloadModel` nodes already consume — none of those node classes are
touched by this epic.

## Specs

_Filled by `beacon specify --epic llamacpp-integration` / `/speckit-specify`
once this epic is accepted._

## ADRs

- project-management/ADRs/ADR-007-llm-provider-adapter-pattern.md — decided during the prerequisite epic; this epic implements the second `LLMProvider` the ADR anticipated

## Success criteria

- `LlamaCppProvider` implements the `LLMProvider` protocol from the prerequisite epic:
  - `list_models()` via `GET /models`, surfacing native status (`unloaded`/`loading`/`loaded`/`sleeping`/`downloading`) directly — no normalization needed, since llama.cpp's vocabulary is the `ModelStatus` enum's superset
  - `load_model()` / `unload_model()` via `POST /models/load` / `POST /models/unload`
  - `chat_structured()` via the same shared `pydantic-ai` mechanism as `OllamaProvider`, `OpenAIProvider(base_url=<llama-server host>/v1)` — no new structured-output code, just a different `base_url`
- `LlamaCppClient` config node (reuses the [ADR-005](../../ADRs/ADR-005-ollama-host-config-via-client-node.md) config-node pattern), outputs the same `LLM_CLIENT` socket type `OllamaClient` does
- No new node classes for model selection, load/unload, or chat — the generic `LLMModelSelector`, `LLMLoadModel`, `LLMUnloadModel`, and `ChatCompletion` nodes from the prerequisite epic work unchanged once a `LlamaCppClient` is wired in
- `LlamaCppClient` registered in `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS`
- Test coverage for `LlamaCppProvider` mirrors the `OllamaProvider` test conventions established in the prerequisite epic
- No new runtime dependencies beyond what the prerequisite epic already introduced (`aiohttp` for model management, `pydantic-ai`/`openai` for chat)
- CI smoke test passes

## Non-goals

- No support for llama-server's non-router single-model launch mode (`-m`) — router mode only, since that's what gives load/unload parity with Ollama
- No GPU inference optimisation or quantisation tuning — CPU-first dev harness, consistent with the Ollama epic's own non-goal
- No auth/TLS/remote-serving hardening — localhost/configurable host via client node only, consistent with the Ollama epic
- No ComfyUI Manager registry listing in this epic
- No changes to the generic nodes or `LLMProvider` protocol themselves — if llama.cpp's router mode needs something the protocol doesn't support, that's a protocol change scoped back into the prerequisite epic's follow-up, not silently special-cased here

## Notes

Router mode is a deployment prerequisite, not something comfydv configures:
the user must launch `llama-server` with `--models-dir`/`--models-preset`
themselves. Document this clearly in the eventual spec/node tooltips.

Reference: [llama.cpp PR #18228](https://github.com/ggml-org/llama.cpp/pull/18228), GitHub issue #15.
