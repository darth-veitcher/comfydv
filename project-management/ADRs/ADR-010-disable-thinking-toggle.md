# ADR-010: `"think"` as an options-carried, per-provider-translated toggle

## Status

> Accepted

_Date:_ 2026-07-25
_Deciders:_ darth-veitcher

---

## Context

ADR-009's investigation into structured-output reliability surfaced, as a side effect, how expensive a "thinking"-capable model's chain-of-thought reasoning is: on a real workflow, a single agent call could spend 5-7+ minutes and its entire token budget on reasoning before ever producing the requested response. Both Ollama and llama-server can turn this off, but neither exposes it through the generic `options` dict `ChatCompletion` already forwards — each has a completely different, incompatible wire shape:

- **Ollama** — live-tested directly: `"think": false` must be a **top-level** field on `/api/chat` (and `/v1/chat/completions`). Nested inside `options` (`{"options": {"think": false}}`) it's silently ignored — confirmed live (`eval_count: 223` reasoning tokens burned vs. `eval_count: 2` with it top-level). One existing test (`test_multi_turn_receives_context`) already carried `options={"think": False}` in its docstring's stated intent; it was a no-op the whole time.
- **llama.cpp** — not live-tested (no router-mode `llama-server` instance available; user explicitly chose doc-based research over waiting for one). Per `tools/server/README.md`: `chat_template_kwargs: {"enable_thinking": false}` (Qwen3-style HF chat-template convention) and/or `reasoning_effort: "none"` (a more model-agnostic OpenAI-style convention llama-server also accepts) — both as request-body fields on `/v1/chat/completions`, not nested in `options` either.

Two shapes were considered for exposing this from comfydv:

1. **A first-class `ChatCompletion` input + `LLMProvider` protocol parameter** — mirroring how `Message.images` crossed the provider boundary (ADR-008). Initially implemented this way.
2. **A composable `OllamaOption*`-style node merging a `"think"` key into the existing `OLLAMA_OPTIONS` chain**, with each provider popping that one key back out and translating it before building its own request — proposed as a simplification once (1) was drafted, since every other tunable knob already flows through this exact composition pattern and a new top-level node parameter would be the only one that doesn't.

## Decision

Went with option 2. `OllamaOptionDisableThinking` (`src/comfydv/ollama.py`) is a new node, identical in shape to `OllamaOptionTemperature`/`OllamaOptionSeed`/etc.: `disable_thinking: BOOLEAN` (default `True`), merges `{"think": not disable_thinking}` into whatever `OLLAMA_OPTIONS` chain it's wired into. No `ChatCompletion` or `LLMProvider` protocol signature change.

Both providers now start `chat()`/`chat_structured()` by popping `"think"` out of the incoming `options` dict (`_pop_think()`, `ollama_provider.py`, shared by both — a pure function, doesn't mutate the caller's dict) and translate it into their own shape before building the request:

- `OllamaProvider`: sets `payload["think"]` at the top level (both `chat()`'s native `/api/chat` call and `chat_structured()`'s, per ADR-009's native-endpoint rewrite).
- `LlamaCppProvider`: sets `chat_template_kwargs`/`reasoning_effort` — directly in its own hand-rolled `chat()` payload, and via `chat.py`'s `extra_body` (the same mechanism `options` itself uses) for `chat_structured()`, which still shares the pydantic-ai path per ADR-009.

Despite living in `ollama.py` and following the `OllamaOption*` naming convention (matching every other option node in that module, all genuinely Ollama-native and untranslated for llama.cpp — see `LlamaCppProvider.chat()`'s own comment), `"think"` is the one key from that chain **both** providers recognize and translate; it isn't itself Ollama's native wire format, it's a comfydv-level convention that happens to reuse Ollama's own field name since Ollama's is the more literal of the two backends' conventions.

## Consequences

**Easier:**
- One node works for both backends, reusing the exact composition pattern (`OLLAMA_OPTIONS` chaining into `ChatCompletion`'s `options` input) every other tunable parameter already uses — no new socket type, no `ChatCompletion.INPUT_TYPES` change, no `LLMProvider` protocol change.
- Fixes an existing test's stated-but-unfulfilled intent for free: `test_multi_turn_receives_context` and `test_structured_output_against_unreliable_model_stays_schema_valid` already passed `options={"think": False}` and now it actually works.
- Meaningfully faster for any thinking-capable model, and directly reduces the token-budget pressure ADR-009 had to fix around.

**Harder / constrained:**
- The llama.cpp translation is not live-verified — sourced from the server's documented request-body fields, not confirmed against a running `llama-server`. Verify against your own deployment before relying on it; a follow-up should close this gap once an instance is available (the user explicitly chose this tradeoff over waiting).
- `"think"` living among genuinely-Ollama-native `OllamaOption*` nodes (which llama.cpp does *not* translate — see that class's own code comment) is a small naming/mental-model inconsistency: one key out of that whole chain is special-cased by both providers. Documented here and in `_pop_think()`'s own docstring so it doesn't read as an oversight later.

**Debt introduced:**
- None. No new dependency, no new socket type.

## Considered Alternatives

### Alternative A: First-class `ChatCompletion` input + protocol parameter (mirroring `Message.images`, ADR-008)

**Why rejected:** Correct in principle (this is a cross-provider concern needing real translation, exactly like images), but heavier than necessary — a new node input plus a `LLMProvider.chat()`/`chat_structured()` signature change plus threading a new parameter through every call site, when the existing `options` dict composition already has a clean seam (`_pop_think`) for a value that needs per-provider translation before hitting the wire. Started implementing this way; reverted once the composable-option alternative was raised.

### Alternative B: Separate provider-specific nodes (`OllamaOptionDisableThinking` / a llama.cpp-only equivalent)

**Why rejected:** Splits one concept into two nodes for no real benefit — both backends' translation lives in code either way, so there's no cost to having one node recognize the same key on both.

---

## Links

- Related ADRs: [ADR-007](ADR-007-llm-provider-adapter-pattern.md) (the `LLMProvider` boundary this operates within), [ADR-008](ADR-008-multimodal-image-input-across-llmprovider-boundary.md) (the pattern this ADR considered and didn't need — cross-provider concerns don't always require a protocol change), [ADR-009](ADR-009-native-structured-output-mode.md) (the investigation that surfaced how expensive unmanaged thinking is)
- llama.cpp server docs (request-body fields, not live-verified): `tools/server/README.md` in `ggml-org/llama.cpp`
