# Research: LLM Provider Abstraction

All unknowns below were already resolved during DESIGN-phase work on
[ADR-007](../../project-management/ADRs/ADR-007-llm-provider-adapter-pattern.md);
this file consolidates that research for the plan gate rather than re-deriving it.

## Decision: `pydantic-ai` for `chat_structured()`, not hand-rolled tool-calling

**Decision**: Both `OllamaProvider` and the future `LlamaCppProvider` implement
`chat_structured()` via `pydantic-ai`'s `Agent`/`output_type`, called through
`OpenAIProvider(base_url=<host>/v1)`.

**Rationale**: A live research pass against current `pydantic-ai` docs/source
found `httpx` is a base dependency of `pydantic-ai-slim` itself (not merely
pulled in by an OpenAI extra), and `openai`+`tiktoken` are required for any
OpenAI-compatible provider — a fixed, one-time dependency tax rather than a
per-backend one. `pydantic.create_model()`-built `BaseModel` subclasses
(comfydv's existing dynamic-schema pattern) work as `output_type` with no
special-casing. `OpenAIProvider(base_url=...)` is one generic code path both
Ollama's and llama.cpp's OpenAI-compatible `/v1/chat/completions` reach
identically.

**Alternatives considered**: hand-roll llama.cpp's structured output too
(duplicates [ADR-006](../../project-management/ADRs/ADR-006-structured-ollama-output-tool-calling-not-pydantic-ai.md)'s
mechanism — rejected, defeats the DRY goal); extract a shared aiohttp-based
helper with no new dependencies (rejected — forces re-deriving pydantic-ai's
retry/validation machinery by hand for no benefit now that two backends exist
to amortize the dependency cost against).

## Decision: aiohttp stays authoritative for model-management REST calls

**Decision**: `list_models()` / `load_model()` / `unload_model()` on every
provider use `aiohttp` — no dependency change from the existing Ollama
integration for this surface.

**Rationale**: [ADR-004](../../project-management/ADRs/ADR-004-aiohttp-over-httpx-for-ollama.md)'s
reasoning (ComfyUI's own server is aiohttp-based; httpx was an unjustified
addition) still applies fully to REST calls that don't need pydantic-ai's
machinery. ADR-007 narrows ADR-004's scope to exactly this surface, rather
than superseding it.

**Alternatives considered**: route everything (including model management)
through `pydantic-ai`/httpx for consistency — rejected, pydantic-ai has no
model-lifecycle-management concept (it's a chat/agent framework, not a
generic REST client) and would add no value over plain aiohttp calls that
already exist and work.

## Decision: `LLMProvider` as a `Protocol` implemented by stateful provider classes

**Decision**: `list_models`/`load_model`/`unload_model`/`chat`/`chat_structured`
are defined as a `typing.Protocol`, implemented by `OllamaProvider` (and later
`LlamaCppProvider`) classes, each constructed once per ComfyUI client node
with the connection's host/headers as instance state.

**Rationale**: This is a Constitution Principle V ("Function Before Class")
gate — classes are only justified when there's shared state a group of
functions would otherwise have to thread through every call. Here there is:
every one of the five protocol methods needs the same host/headers, exactly
the connection config [ADR-005](../../project-management/ADRs/ADR-005-ollama-host-config-via-client-node.md)'s
config-node pattern centralizes. A `Protocol` (structural typing, no
inheritance required) keeps this lightweight — `LlamaCppProvider` doesn't
need to import or subclass `OllamaProvider`, it only needs to match the
method shapes.

**Alternatives considered**: module-level functions taking host/headers as
explicit parameters on every call — rejected, this reintroduces the exact
per-call-site repetition ADR-005 eliminated, and loses the ability for a
ComfyUI `LLM_CLIENT` socket to carry one opaque object implementing the
protocol (functions can't be typed as a socket payload the way an object
implementing a `Protocol` can).

## Decision: behavior-preserving migration, verified against existing tests

**Decision**: `tests/test_ollama.py`'s existing assertions (retry bounds,
required-string validation, error messages) are the acceptance bar for the
migrated `OllamaProvider.chat_structured()` — this is a mechanism swap, not a
new capability, per the parent epic's Non-goals and spec FR-008.

**Rationale**: Constitution Principle III (Test-First) and the epic's
explicit framing of this as the riskiest change in the whole llama.cpp
proposal (touches a Done, shipped epic's code) both point the same way: the
existing test suite is the regression oracle, not a new one written from
scratch.

## Testing approach

Per Constitution Principle IV (Graceful Degradation Outside ComfyUI), the new
`src/comfydv/_llm/` package must not import `comfy`/`server` at module scope,
matching `ollama.py`'s existing runtime-guarded pattern. Unit tests mock
`aiohttp`/`pydantic-ai` calls (no live server required, matching
`tests/test_ollama.py`'s existing convention); the `integration` pytest
marker (already defined in `pyproject.toml`, "requiring live Ollama at
localhost:11434") is reused, not redefined, for tests that exercise a real
local server.
