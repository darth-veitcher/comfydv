# ADR-009: Provider-specific structured output — NativeOutput for llama.cpp, hand-rolled native `/api/chat` for Ollama

## Status

> Accepted

_Date:_ 2026-07-25
_Deciders:_ darth-veitcher

---

## Context

`chat_structured()` (`src/comfydv/_llm/chat.py`, ADR-007) builds its `pydantic-ai` `Agent` with a bare `output_type=schema`. Passing a raw `pydantic.BaseModel` subclass this way makes `pydantic-ai` default to **tool-calling** (a synthetic forced function call) for structured output — inherited silently from ADR-007's move to `pydantic-ai`, never a deliberate re-decision. ADR-007 doesn't discuss output-mode choice at all.

Testing a real multi-agent ComfyUI workflow (`workflows/ltx-i2v-pipeline.json`) against a live local Ollama server surfaced this as a real reliability problem: against a "thinking"-capable model (`qwen3.5:9b`), tool-calling failed consistently — the model spent its entire token budget on internal chain-of-thought reasoning and never emitted the tool call, so every attempt failed pydantic validation ("token limit exceeded before any response was generated"), each attempt taking 5-7+ minutes before giving up.

### First fix attempt: `NativeOutput` + a priming call (superseded within this same ADR)

`pydantic-ai` 2.9.0 exposes `NativeOutput`, which makes the `Agent` use `response_format: {"type": "json_schema", ...}` over the OpenAI-compatible endpoint instead of tool-calling. Live-tested directly against Ollama via `curl` before touching code: `/v1/chat/completions` with `response_format: json_schema` returned clean, schema-valid JSON, with the model's reasoning in a separate `message.reasoning` field — fast, and reasoning no longer competed with structured output for token budget. This part of the fix is real and is kept — see Decision §1.

A second, separate problem was also found: Ollama's OpenAI-compatible endpoint doesn't honor a per-request `options` override (e.g. `num_ctx`) — sending the same request to native `/api/chat` reloaded the model at the requested context size; `/v1/chat/completions` silently kept whatever was already loaded. The first fix attempt worked around this with a priming call: hit native `/api/generate` with the desired `options` immediately before the real `/v1/chat/completions` request, on the theory that Ollama would keep the just-loaded context for the next call.

**This did not work, and the failure mode looked exactly like the original bug** — confirmed while re-testing the actual workflow end-to-end (`workflows/ltx-i2v-pipeline.json`, Agent 2 "Scene Grounder": long system prompt + 9-property schema + image), which kept failing with the identical "token limit exceeded" error even after the priming fix landed, tests passed, and `max_tokens`/`num_ctx`/`timeout_secs` were all raised generously. Isolated the exact mechanism with a direct, non-ComfyUI-mediated `curl` sequence:

1. `POST /api/generate` with `options: {num_ctx: 20480}`, `keep_alive: -1` → confirmed via `GET /api/ps`: `context_length: 20480`, loaded "forever".
2. Immediately `POST /v1/chat/completions` for the same model — **even with the identical `options: {num_ctx: 20480}` included in that request's body** → `GET /api/ps` immediately after: `context_length: 4096` (back to default), `expires_at` reset to a normal ~5-minute keep-alive.

So `/v1/chat/completions` doesn't merely *ignore* `options.num_ctx` — every call to it silently **reloads the model at the default context size**, discarding whatever was primed, regardless of what that same call's own `options` field says. A priming call immediately before the real request is structurally incapable of working, because the real request itself is what undoes the priming.

Re-ran the same sequence against native `/api/chat` instead of `/v1/chat/completions`: the primed `context_length: 20480` was preserved through and after the call. Native `/api/chat` also accepts `"format": <json schema>` directly, giving grammar-constrained structured output in the same request that correctly honors `options` — no separate priming call needed at all.

### Re-litigating ADR-006's model concern

This also revisits [ADR-006](ADR-006-structured-ollama-output-tool-calling-not-pydantic-ai.md), which rejected native `format`-based output — but its rejection was scoped to one specific model, `lukey03/qwen3.5-9b-abliterated-vision`, whose degenerate chat template silently ignored the constraint. ADR-006 explicitly flagged this as revisitable: *"If well-behaved-model testing later shows native `format` is meaningfully more reliable in the common case, this decision should be revisited rather than treated as permanent."* Re-tested that exact model against native structured output: it no longer silently ignores the constraint (ADR-006's specific failure mode) — it returns schema-valid JSON, but the *content* is still garbled (`"ponáp∵49\n"` instead of the requested `"pong"`), consistent with ADR-006's "degenerate tokenizer" diagnosis. That model was also already failing under the tool-calling path (hanging without completing, observed live during this same investigation). So neither part of this decision regresses that model — it was already unusable for structured output either way. `structured_output` has no production users yet, so there is no back-compat concern in making this change.

## Decision

**1. `LlamaCppProvider` keeps the shared `pydantic-ai` path, switched to `NativeOutput`.** `chat.py`'s `_build_agent()` builds `Agent(chat_model, output_type=NativeOutput(schema), retries=0)` instead of a bare `output_type=schema`. llama-server's OpenAI-compatible endpoint is its genuine native structured-output surface (no equivalent context-reload bug found or expected — llama-server's context is fixed at process launch via `--ctx-size`, not a per-request concern, so there's nothing for a request to silently reset), so the shared-implementation architecture from ADR-007 stays intact for this provider.

**2. `OllamaProvider.chat_structured()` no longer uses `chat.py` at all.** It hand-rolls its own call to Ollama's **native** `/api/chat` with a `"format"` JSON schema, mirroring the request-building and retry/validation contract `chat.py` established (bounded retries 0–5, `RuntimeError` naming the model/attempt-count/truncated-response on exhaustion) but without pydantic-ai in the loop for this provider — there is no bare-metal native-JSON-schema mode in pydantic-ai's OpenAI-compatible model class to point at Ollama's native (non-OpenAI-shaped) endpoint, so this is a direct `_post_json` call, parsed with `schema.model_validate_json(...)`, retried on `pydantic.ValidationError` (which pydantic v2 also raises for malformed JSON, not just schema mismatches). `options` (from `OllamaOption*` nodes) is included directly in this same request's `"options"` field and is correctly honored, since it's the native endpoint — no separate priming call, because none is needed: structured output and context sizing now apply atomically in one request.

The retry/validation contract itself (bounded retries, `RuntimeError` naming the model/attempt-count/truncated-response on exhaustion) is unchanged and now implemented twice — once in `chat.py` for llama.cpp, once directly in `ollama_provider.py` for Ollama — rather than shared, which is the real cost of this decision (see Consequences).

## Consequences

**Easier:**
- Structured output is now reliable against "thinking"-capable models on both providers — reasoning and structured content are separate response fields (`message.reasoning`/`message.thinking` vs `message.content`) under both `NativeOutput` and Ollama's native `format`, rather than competing for the same token stream under tool-calling.
- `num_ctx` and other Ollama-native options now actually apply to structured-output requests — genuinely fixed this time, confirmed by re-running the actual failing workflow agent, not just by a passing test suite (the first fix attempt passed every test and still didn't work end-to-end).
- Meaningfully faster in the success case than tool-calling against a thinking model.
- Closes ADR-006's own explicit "revisit later" flag with concrete evidence rather than leaving it open indefinitely.

**Harder / constrained:**
- `OllamaProvider` and `LlamaCppProvider` now have two independent structured-output implementations instead of one shared one — ADR-007's "share one implementation" goal no longer holds for this piece. A future structured-output feature (e.g. plumbing reasoning content back to the caller) needs to land in both places.
- Structured output guarantees schema-*shape* validity, not semantic correctness, on both providers now — a genuinely broken model (degenerate tokenizer, as with the abliterated test model) can still return valid-JSON garbage instead of raising a clear error. Downstream consumers should not treat "returned without error" as "returned correct content" for low-quality/unreliable models.
- Ollama's native `/api/chat` endpoint's `"format"` field is only checked against top-level `type`/`properties`/`required` the same way the OpenAI-compat `response_format` was — no change to `_build_structured_model`'s shallow-schema behavior in `ollama.py`.

**Debt introduced:**
- Two structured-output code paths (per provider) instead of one shared one, as noted above — accepted because the two providers' actual constraints (Ollama's context-reset-per-OpenAI-compat-call bug vs. llama-server's fixed-at-launch context) are genuinely different, not incidentally different.
- Not addressed here (flagged for a future ADR if pursued): a model's reasoning/thinking content is available (`message.reasoning` natively for Ollama, parsed into pydantic-ai's `ThinkingPart` for llama.cpp) but discarded by both `chat_structured()` implementations, which only return the validated schema instance. Plumbing this back to `ChatCompletion` as a node output would need a `LLMProvider.chat_structured()` return-type change — a `Protocol`-level change affecting both providers, out of scope here.
- Not addressed here (pre-existing, unrelated): `LlamaCppProvider.chat()`'s own code comments already note that `OllamaOption*` nodes emit Ollama-native option names llama-server's OpenAI-compatible endpoint doesn't recognize — an accepted gap from the llama.cpp integration epic, unrelated to this decision.

## Considered Alternatives

### Alternative A: `NativeOutput` + priming call for both providers (the first fix attempt)

**Why rejected:** This is what ADR-009 originally shipped as. It passed every test (including a new one added specifically for the priming call) and one successful live single-agent ComfyUI run, but failed to actually fix the real workflow — confirmed by re-running the full pipeline and hitting the identical original failure on a later, more complex agent. Root-caused only after that: `/v1/chat/completions` unconditionally reloads the model at default context on *every* call, so priming immediately before the real call is undone by the real call itself. No amount of retrying, raising `max_tokens`, or raising `timeout_secs` fixes a context-size problem that the request itself keeps resetting.

### Alternative B: Fully switch both providers off `pydantic-ai`, hand-roll native structured output everywhere

**Why rejected:** Unnecessary for `LlamaCppProvider` — no evidence llama-server's OpenAI-compatible endpoint has Ollama's context-reset behavior (its context is fixed at process launch regardless of request), so `NativeOutput` over the existing shared path is strictly simpler there and keeps ADR-007's sharing goal intact for at least one provider.

### Alternative C: Do nothing, document Ollama's context-reset behavior as a known limitation

**Why rejected:** The underlying failure mode (indefinite-looking hangs, or outright failures, against any Ollama model needing more than the default 4096-token context while using structured output) is common enough — any long system prompt plus a non-trivial schema hits it — that documenting around it would leave `structured_output=True` effectively broken for Ollama in exactly the cases where structured output is most useful (complex, multi-field extraction tasks).

---

## Links

- Related ADRs: [ADR-006](ADR-006-structured-ollama-output-tool-calling-not-pydantic-ai.md) (superseded rationale, not superseded status — ADR-006's tool-calling-vs-native evidence and reasoning stand as historical record; this ADR only revisits its "revisit later" flag), [ADR-007](ADR-007-llm-provider-adapter-pattern.md) (provider abstraction this decision partially steps outside of, for Ollama only)
- Discovered while building/testing: `workflows/ltx-i2v-pipeline.json`
