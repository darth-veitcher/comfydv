# ADR-006: Structured Ollama output via OpenAI-compatible tool-calling + dynamic pydantic validation, not pydantic-ai

## Status

> Superseded by [ADR-007](ADR-007-llm-provider-adapter-pattern.md)

_Date:_ 2026-07-09
_Deciders:_ darth-veitcher

---

## Context

`OllamaChatCompletion` sends free-text prompts to Ollama's `/api/chat` and
returns `result["message"]["content"]` as-is, with no constraint on what the
model may emit. In practice this is unreliable in three concrete ways:
models prepend commentary ("Here you are:"), wrap responses in ` ``` ` code
fences, or occasionally return blank content — all things prompt wording
alone (e.g. a stricter `system` message) cannot reliably prevent, since it
only *asks* the model to behave, it doesn't constrain what tokens the
decoder is able to produce.

The obvious library to reach for is `pydantic-ai`, which offers structured,
validated LLM output as a first-class feature. Its Ollama support, however,
goes through an OpenAI-compatible client — which pulls in the `openai` SDK,
which depends on `httpx`. This directly reverses
[ADR-004](ADR-004-aiohttp-over-httpx-for-ollama.md), which explicitly
rejected `httpx` as "a new runtime dep for functionality aiohttp already
provides" (ComfyUI's own server is aiohttp-based, so aiohttp is a guaranteed
transitive dependency; httpx is not).

Two Ollama-native mechanisms can force structured output without a new HTTP
client, since both are reachable over plain JSON POST via the existing
`aiohttp`-based `_post_json`:

1. **Native `/api/chat` `"format"` field** — a JSON Schema that constrains
   **decoding itself** (grammar-constrained sampling): the model's sampler
   is restricted to only emit tokens matching the schema.
2. **OpenAI-compatible `/v1/chat/completions` tool-calling** — a `tools`
   array plus `tool_choice` forcing a single named function call, relying on
   the model's own trained function-calling behavior rather than a
   grammar-to-token mapping.

Both were tried against a real local model
(`lukey03/qwen3.5-9b-abliterated-vision`) during implementation. The native
`format` field was silently ignored — the model returned plain unstructured
text (`"pong"`) despite the schema constraint, reproduced twice. Inspecting
`/api/show` revealed this model's `TEMPLATE` is a degenerate `{{ .Prompt }}`
with no role/message structure — consistent with a community "abliteration"
process having modified the tokenizer/vocab in a way that breaks Ollama's
grammar-to-token mapping, causing it to silently fall back to unconstrained
generation instead of erroring. Tool-calling doesn't depend on that mapping;
it succeeded on its first test against the same model. (A follow-up
tool-calling call with `options` included did also fail — this specific
model appears broadly unreliable, consistent with a degraded fine-tune, so
this evidence is suggestive rather than conclusive. No second generative
model was available locally to get a cleaner signal.)

## Decision

Use Ollama's OpenAI-compatible tool-calling (`/v1/chat/completions`,
`tools`/`tool_choice` forcing a single call) for `structured_output=True`
requests, sent through the existing `_post_json` helper — no new HTTP
client, no `pydantic-ai`, no `openai` SDK. Non-structured requests are
completely unaffected and keep using native `/api/chat`.

Use plain `pydantic` (not `pydantic-ai`) purely as a validation layer:
given the user-supplied JSON Schema (`output_schema` input on
`OllamaChatCompletion`), dynamically build a `pydantic.BaseModel` via
`pydantic.create_model(...)` and validate/parse the tool call's `arguments`
JSON against it. Required *string* fields get `min_length=1` — JSON
Schema's `"required"` only checks presence, so a model could satisfy it
with `""`, silently reintroducing the "blank output" problem. On validation
failure (invalid JSON, missing/empty required field, or the model not
calling the tool at all — observed to happen even with `tool_choice`
forcing it), retry with fresh network calls (bounded by a `max_retries`
input, clamped to 0–5); if every attempt fails, raise a clear
`RuntimeError` naming the model, the attempt count, and a truncated
snippet of the last invalid response — never silently degrade to
unvalidated content.

This is opt-in: a new `structured_output: BOOLEAN` input on the existing
`OllamaChatCompletion` node, default `False`. When off, behavior is
unchanged — no `tools`/`tool_choice` sent, native `/api/chat` used, no
dynamic outputs, `RETURN_TYPES` stays the original fixed 3-tuple. When on,
one additional ComfyUI output socket is exposed per schema property
(mirroring `FormatString`'s existing dynamic-output-socket pattern via
`unique_id`/`RETURN_TYPES` mutation), so downstream nodes can consume
individually typed fields instead of parsing JSON themselves.

## Consequences

**Easier:**
- Fixes the three concrete unreliability problems without depending on a
  model/tokenizer-sensitive grammar-constraint mechanism that was observed
  to fail silently on at least one real model.
- No new HTTP stack: `pydantic` is a validation-only dependency, not a
  client library. ADR-004's aiohttp-only stance is preserved.
- Fully backward compatible — `structured_output` defaults off, and
  non-structured requests still use native `/api/chat` exactly as before.

**Harder / constrained:**
- Tool-calling depends on the model having usable trained function-calling
  behavior. Models with no tool-calling training may perform worse here
  than they would under grammar-constrained `format` decoding — this
  repo's only local test model was itself too unreliable to fully confirm
  either mechanism's ceiling. If well-behaved-model testing later shows
  native `format` is meaningfully more reliable in the common case, this
  decision should be revisited rather than treated as permanent.
- Only a flat `properties: {name: {type: ...}}` shape is interpreted into
  typed ComfyUI sockets. Complex JSON Schema constructs (`$ref`,
  `oneOf`/`anyOf`/`allOf`, `enum`, nested `object`/`array` item schemas) are
  still forwarded to Ollama verbatim as the tool's `parameters`, but
  comfydv's own type mapping falls back to `STRING` for anything it doesn't
  recognize — no nested typed sockets.
- `RETURN_TYPES`/`RETURN_NAMES` are class-level state, shared across every
  `OllamaChatCompletion` instance in a graph (same accepted limitation
  `FormatString.update_widget` already ships with) — the first execution
  after toggling `structured_output` or editing `output_schema` may show
  stale downstream socket typing until it runs once.
- Neither mechanism is guaranteed 100% across all versions/models — hence
  the retry-then-raise defense-in-depth, rather than trusting either
  constraint blindly.

**Debt introduced:**
- None. `pydantic` is a widely-used, low-conflict-risk dependency; ComfyUI
  itself is expected to already bundle it for its own API layer, though
  this repo lists it explicitly in both `pyproject.toml` and
  `requirements.txt` per ADR-003 rather than assume so.

## Considered Alternatives

### Alternative A: `pydantic-ai`

**Why rejected:** Its Ollama support goes through an OpenAI-compatible
client, reintroducing `httpx` + the `openai` SDK — the exact dependency
ADR-004 evaluated and rejected. The reliability benefit it offers is the
same tool-calling/validation mechanism this ADR adopts directly over plain
`aiohttp`, without the added dependency weight.

### Alternative B: Native `/api/chat` `"format"` field (JSON-Schema-constrained decoding)

**Why rejected as primary:** Theoretically the stronger guarantee — a
sampler-level constraint rather than learned behavior — and remains a
reasonable mechanism for well-behaved models. Rejected here because it
failed outright (silently ignored, not even erroring) against the one real
model available for testing, traced to that model's modified tokenizer
breaking Ollama's grammar-to-token mapping. Tool-calling succeeded where it
failed. See "Harder / constrained" above — this may be revisited if
broader testing shows native `format` is more reliable in the common case.

### Alternative C: Prompt-only enforcement (stricter `system` message)

**Why rejected:** `system` already exists as an input and users can already
try this — it's what led to the reported problem in the first place.
Wording can reduce commentary/fences/blank output but cannot guarantee
their absence, since nothing constrains the actual token stream.

### Alternative D: Response-side post-processing (regex-strip fences/preamble)

**Why rejected as the primary fix:** Cheap, but fundamentally reactive —
it can strip a fence wrapper after the fact but can't recover genuinely
blank output, and heuristics for "commentary" are unreliable across models.
Not pursued as a fallback either, to keep this change minimal and avoid two
competing "make output clean" mechanisms with unclear precedence.

---

## Links

- Related ADRs: [ADR-003](ADR-003-requirements-txt-authoring-policy.md), [ADR-004](ADR-004-aiohttp-over-httpx-for-ollama.md), [ADR-005](ADR-005-ollama-host-config-via-client-node.md)
- Originating epic (archived, scope predates this decision): `project-management/Roadmap/epics/archive/ollama-integration.md`
