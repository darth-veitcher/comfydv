# ADR-007: LLMProvider adapter pattern shared across Ollama and llama.cpp

## Status

> Accepted

_Date:_ 2026-07-11
_Deciders:_ darth-veitcher

---

## Context

GitHub issue #15 asks comfydv to add ComfyUI nodes for llama.cpp, mirroring
the existing Ollama integration
(`project-management/Roadmap/epics/archive/ollama-integration.md`), and
explicitly poses the design question: separate nodes per backend, or an
adapter pattern that shares code? It's motivated by llama.cpp's new "router
mode" (`llama-server --models-dir <dir>`, via
[llama.cpp PR #18228](https://github.com/ggml-org/llama.cpp/pull/18228),
merged 2025-12-21), which exposes `GET /models`, `POST /models/load`,
`POST /models/unload`, and `--sleep-idle-seconds` auto-unload — giving
llama.cpp the same manual load/unload memory-management primitives comfydv
already relies on for Ollama.

`src/comfydv/ollama.py` (1056 lines, 17 node classes) has no abstraction
layer today: two module-level free functions (`_post_json`, `_fetch_models`)
are called directly by every node, with Ollama endpoint paths hardcoded
inline; socket types (`OLLAMA_CLIENT`, `OLLAMA_OPTIONS`, `OLLAMA_HISTORY`)
and `PromptServer` routes (`/dv/ollama/...`) are Ollama-named throughout.

**Two things needed resolving to answer issue #15's question honestly:**

1. **Does model lifecycle management (list/load/unload) actually converge
   between backends, or not?** At the wire-protocol level, no: Ollama uses
   `/api/tags` + a per-request `keep_alive` TTL on `/api/generate`;
   llama.cpp router mode uses `/models` + explicit `/models/load` /
   `/models/unload` + named status states
   (`unloaded`/`loading`/`loaded`/`sleeping`/`downloading`). Judged at that
   level, a shared interface looks forced. But at the *conceptual* level,
   both APIs support exactly the same four operations — list models with
   status, load a model, unload a model, and generate/chat against a loaded
   model — just with different mechanics. Ollama's `keep_alive`-based
   load/unload already *is* `load_model()`/`unload_model()`, mechanically
   implemented as a side effect of a `/api/generate` call rather than a
   dedicated endpoint. A `Protocol` boundary at the operation level, not the
   wire-format level, fits both backends without forcing anything.

2. **Does `pydantic-ai` make sense now that a second backend exists?**
   [ADR-006](ADR-006-structured-ollama-output-tool-calling-not-pydantic-ai.md)
   (2026-07-09) rejected `pydantic-ai` for a single backend because its
   Ollama support pulls in `httpx` + the `openai` SDK, reversing
   [ADR-004](ADR-004-aiohttp-over-httpx-for-ollama.md)'s aiohttp-only
   stance. A research pass against current `pydantic-ai` docs/source (this
   moves fast and postdates training data, so verified live rather than
   assumed) found: `httpx` is a **base dependency of `pydantic-ai-slim`
   itself**, not merely pulled in by an OpenAI-specific extra; `openai` SDK
   + `tiktoken` are additionally required to reach any OpenAI-compatible
   backend; there is no aiohttp transport option anywhere in pydantic-ai.
   This is a **fixed, one-time dependency tax**, not one that grows per
   backend. Separately, `pydantic.create_model()`-built `BaseModel`
   subclasses (comfydv's existing pattern for validating against a
   user-supplied JSON-Schema string at workflow-execution time) work as
   pydantic-ai's `output_type` with no special-casing — the dynamic-schema
   requirement is not a blocker. And `OpenAIProvider(base_url=...)` is the
   exact generic mechanism pydantic-ai's own `OllamaProvider` is built on
   internally, so llama.cpp's `/v1/chat/completions` reaches an identical
   code path with a different `base_url` — genuinely shared implementation,
   not just a shared shape.

Both findings point the same direction: a real `Protocol`-based adapter,
with `pydantic-ai` as the mechanism behind its structured-output method.

## Decision

Define a `LLMProvider` `Protocol` (new internal module, e.g.
`src/comfydv/_llm/provider.py`) with the common surface:

```python
class LLMProvider(Protocol):
    async def list_models(self) -> list[ModelInfo]: ...
    async def load_model(self, model: str) -> None: ...
    async def unload_model(self, model: str) -> None: ...
    async def chat(self, model: str, messages: ..., options: ...) -> str: ...
    async def chat_structured(self, model: str, messages: ..., schema: type[BaseModel], options: ...) -> BaseModel: ...
```

`OllamaProvider` and `LlamaCppProvider` each implement it, absorbing their
own REST mechanics internally (Ollama: `/api/tags`, `/api/generate` with
`keep_alive`; llama.cpp: `/models`, `/models/load`, `/models/unload`) via
`aiohttp`, unchanged from ADR-004's stance for non-chat calls. Both
implement `chat_structured()` via the same `pydantic-ai` `Agent`/
`output_type` call through `OpenAIProvider(base_url=...)` — one shared
implementation, differing only in `base_url` and model name.

ComfyUI nodes become **generic, not per-backend**: `OllamaClient` and
`LlamaCppClient` both output the same `LLM_CLIENT` socket type (each
internally constructs the matching provider); a single `LLMModelSelector`,
`LLMLoadModel`, `LLMUnloadModel`, and `ChatCompletion` node operate against
`LLM_CLIENT` generically. Swapping providers on the canvas means rewiring
which client node feeds the chat/management nodes, not swapping node
classes — this is the direct answer to issue #15's question: **adapter
pattern**, implemented as a protocol boundary at the operation level.

This **supersedes ADR-006**: `OllamaChatCompletion`'s `structured_output=True`
path moves from hand-rolled tool-calling to `pydantic-ai` via the protocol.

This **narrows ADR-004's scope**: aiohttp remains the transport for every
non-chat REST call inside each provider; `httpx`/`openai` enter the
dependency tree scoped specifically to `chat_structured()`, via
`pydantic-ai`.

**Documented approximation:** `ModelStatus` includes `sleeping` and
`downloading`, states that exist in llama.cpp router mode but not in
Ollama's API. `OllamaProvider.list_models()` normalizes into the same enum
rather than inventing Ollama-specific states — a model that's resident and
idle maps to `loaded` (Ollama has no distinct "kept warm but not serving"
signal via this API), and `downloading` is simply never emitted by
`OllamaProvider` (Ollama's pull/download flow is out of scope per the
original Ollama epic's non-goals). This is an accepted, explicit
approximation, not a silent gap.

**Confirmed:** adopting generic node/socket names (`LLM_CLIENT`,
`ChatCompletion`, etc.) means renaming away from `OLLAMA_CLIENT`,
`OllamaChatCompletion`, and similar — a breaking change for any saved
workflow using the current names. The Ollama integration shipped
2026-07-04, so the blast radius is small. Confirmed 2026-07-11: rename in
place now rather than carry Ollama-prefixed names forward or maintain
deprecated aliases indefinitely.

## Consequences

**Easier:**
- Issue #15's question gets a real answer: one generic node set works with
  any backend that implements `LLMProvider`, including future ones (a third
  local server, or a hosted OpenAI/Anthropic provider) without new node
  classes.
- One implementation of tool-calling/structured-output logic instead of
  duplicating it per backend; `pydantic-ai` brings built-in retry/validation
  machinery, replacing ADR-006's hand-rolled retry loop.
- The protocol boundary keeps each backend's REST quirks contained inside
  its provider — the graph never has to know Ollama uses `keep_alive` while
  llama.cpp uses explicit load/unload endpoints.

**Harder / constrained:**
- New dependencies (`pydantic-ai`, `openai`, `tiktoken`, `httpx`) land in a
  project that was previously aiohttp-only.
- This is a nontrivial migration of tested, shipped Ollama code (the
  `ollama-integration` epic is Done) — not purely additive work. Must be
  proven regression-safe before it's trusted as the foundation for
  llama.cpp.
- `ModelStatus` is not perfectly symmetric across backends — the
  `sleeping`/`downloading` states are llama.cpp-only in practice; documented
  above, but still a leak of llama.cpp's richer vocabulary into a
  nominally-generic type.
- The node/socket rename is a breaking change for existing saved workflows —
  confirmed acceptable given the small blast radius (see above).

**Debt introduced:**
- None deliberately, contingent on the migration preserving existing
  Ollama behavior exactly (verified against `tests/test_ollama.py`).

## Considered Alternatives

### Alternative A: Shared `pydantic-ai` chat layer only; separate per-backend management nodes

**Why rejected:** This was the first-pass design — judged convergence at
the REST wire-protocol level (Ollama's `/api/tags`+`keep_alive` vs.
llama.cpp's `/models`+`/models/load`+`/models/unload` don't look alike) and
concluded a shared interface would be forced. That framing was wrong: the
right level to judge convergence is the *operation* (list/load/unload/chat),
not the wire format. Both backends genuinely support the same four
operations; only their REST mechanics differ, and those differences belong
inside each provider implementation, not on the graph.

### Alternative B: Hand-roll llama.cpp's structured output too (duplicate ADR-006's approach)

**Why rejected:** Two independent implementations of the same
OpenAI-compatible tool-calling mechanism is the DRY violation issue #15
raises in the first place, with no offsetting benefit now that a second
backend exists to justify a shared layer.

### Alternative C: Keep `pydantic-ai` rejected; extract a shared aiohttp-based internal helper instead

**Why rejected:** Avoids new dependencies entirely, but forces re-deriving
`pydantic-ai`'s retry/validation machinery by hand for no benefit beyond
dependency-avoidance — and doesn't change the model-management convergence
question at all (that's orthogonal to which HTTP client the chat path
uses). The one-time dependency tax is judged worth paying for the fuller
abstraction, now that two backends exist to amortize it against.

---

## Links

- Related epics: `project-management/Roadmap/epics/llm-provider-abstraction.md`, `project-management/Roadmap/epics/llamacpp-integration.md`
- Related ADRs: [ADR-004](ADR-004-aiohttp-over-httpx-for-ollama.md) (narrowed), [ADR-005](ADR-005-ollama-host-config-via-client-node.md) (client-node pattern generalized to `LLM_CLIENT`), [ADR-006](ADR-006-structured-ollama-output-tool-calling-not-pydantic-ai.md) (superseded)
- External reference: [llama.cpp PR #18228](https://github.com/ggml-org/llama.cpp/pull/18228) (router mode, merged 2025-12-21), GitHub issue #15
