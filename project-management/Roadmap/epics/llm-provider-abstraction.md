# Epic: LLM Provider Abstraction

## Status
Active — started 2026-07-11

## Why now

GitHub issue #15 asks for llama.cpp support "similar to Ollama," and
explicitly raises the question of separate nodes vs. an adapter pattern.
[ADR-007](../../ADRs/ADR-007-llm-provider-adapter-pattern.md) answers that
with a real adapter: a `LLMProvider` protocol (`list_models`/`load_model`/
`unload_model`/`chat`/`chat_structured`) that any backend implements, backing
a set of generic ComfyUI nodes (`ChatCompletion`, `LLMModelSelector`,
`LLMLoadModel`, `LLMUnloadModel`) that work with whichever provider is wired
in. For that to be real — not just aspirational — the existing Ollama
integration has to migrate onto the protocol first, including moving its
structured-output mechanism from ADR-006's hand-rolled tool-calling onto
`pydantic-ai`. This epic is that migration; it's a prerequisite for
`llamacpp-integration`, not additive scope on top of it — building
llama.cpp against generic nodes that don't exist yet isn't possible.

## Dependencies

_None to start — this epic can begin immediately._ The
`llamacpp-integration` epic depends on this one landing first: its
`LlamaCppProvider` implements the protocol this epic defines, and its
`LlamaCppClient` node emits the same `LLM_CLIENT` socket type this epic
introduces.

## Specs

_Filled by `beacon specify --epic llm-provider-abstraction` /
`/speckit-specify` once this epic is accepted._

- specs/007-llm-provider-abstraction/
## ADRs

- project-management/ADRs/ADR-007-llm-provider-adapter-pattern.md — defines the `LLMProvider` protocol as the adapter boundary; supersedes ADR-006; narrows ADR-004's scope to non-chat REST calls per-provider

## Success criteria

- `LLMProvider` protocol defined (new internal module, e.g. `src/comfydv/_llm/provider.py`): `list_models()`, `load_model(name)`, `unload_model(name)`, `chat(...)`, `chat_structured(..., schema)`
- `ModelStatus` enum defined (`unloaded`/`loading`/`loaded`/`sleeping`/`downloading`) per ADR-007's documented approximation
- `OllamaProvider` implements the protocol, wrapping all existing Ollama REST logic (`/api/tags`, `/api/generate` with `keep_alive`) over `aiohttp` — behavior-preserving port of the current `_post_json`/`_fetch_models` logic, not a rewrite of the underlying calls
- `chat_structured()` implemented via `pydantic-ai`'s `Agent`/`output_type`, called through `OpenAIProvider(base_url=<host>/v1)`, using the same dynamic `pydantic.create_model()`-from-JSON-Schema pattern as ADR-006 — same dynamic-socket UX, same retry/validation contract (bounded `max_retries`, required-string-non-empty check, clear `RuntimeError` on exhaustion)
- `pydantic-ai` and `openai` added to `pyproject.toml`, curated into `requirements.txt` per [ADR-003](../../ADRs/ADR-003-requirements-txt-authoring-policy.md)
- Generic ComfyUI nodes replace the current Ollama-specific ones: `OllamaClient` now outputs `LLM_CLIENT` (constructing an `OllamaProvider` internally); `LLMModelSelector`, `LLMLoadModel`, `LLMUnloadModel`, `ChatCompletion` operate against `LLM_CLIENT` generically
- The non-structured-output chat path (native `/api/chat`) is behavior-unchanged
- All existing `tests/test_ollama.py` coverage passes against the migrated implementation (adjusted for renamed node/socket types, unchanged in behavior otherwise)
- Model-management calls remain entirely on `aiohttp`, inside `OllamaProvider` — untouched transport-wise
- CI smoke test passes

## Non-goals

- No `LlamaCppProvider` or llama.cpp nodes in this epic — that's `llamacpp-integration`
- No behavior change to non-structured-output chat
- No tracing/observability integration (e.g. Logfire), even though `pydantic-ai` supports it
- No multi-turn agentic tool use beyond the existing single structured-output call
- No backward-compat aliases for the old `Ollama`-prefixed node/socket names — confirmed 2026-07-11 to rename in place (see ADR-007)

## Notes

This is the riskiest part of the whole llama.cpp proposal: it changes the
implementation of tested, shipped code from a Done epic
(`archive/ollama-integration.md`), not just adding new code, and it's a
breaking rename (`OLLAMA_CLIENT`→`LLM_CLIENT`,
`OllamaChatCompletion`→`ChatCompletion`, etc.) for anyone with saved
workflows using the current node/socket names. Confirmed 2026-07-11 (per
ADR-007): rename in place now — the Ollama integration only shipped
2026-07-04, so the blast radius is small — rather than carrying
`Ollama`-prefixed generic nodes forward or maintaining deprecated aliases
indefinitely.

Recommend an adversarial pass (`/beacon:review` or `/beacon:engineering`)
before merging, specifically checking that the retry/validation contract
from ADR-006's `## Decision` section is preserved exactly by the
`pydantic-ai` reimplementation, and that `OllamaProvider`'s REST calls are a
faithful port of the current `_post_json`/`_fetch_models` logic.

**2026-07-11 — mid-build correction, tracked in [issue #16](https://github.com/darth-veitcher/comfydv/issues/16):**
the Foundational layer (`LLMProvider` protocol + `OllamaProvider` skeleton)
shipped safely, but the planned per-user-story incremental cutover doesn't
hold — `OllamaClient` is a single shared producer for every downstream
Ollama node, so the node-layer rename/cutover (`tasks.md`'s US1 + US3) must
land as one atomic change, not four independent ones. Confirmed by
independent product + engineering review. Re-scoped as its own dedicated
follow-up BUILD session — see `specs/007-llm-provider-abstraction/tasks.md`'s
correction note for full detail. Open question for the next session: does
this take priority over `ux-and-install` (active, 1/4 specs shipped), since
llama.cpp (issue #15) has no deadline.

`pydantic-ai`'s `StructuredDict` (raw-JSON-Schema output, no Python class)
was considered as a lighter-weight alternative to `create_model()` during
research and rejected: it performs no pydantic validation at all, which
would silently drop the "reject blank required strings" safeguard ADR-006
introduced. Stick with `create_model()`-built `BaseModel` subclasses.
