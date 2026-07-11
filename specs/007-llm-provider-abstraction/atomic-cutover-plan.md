# Atomic Cutover Plan: Ollama Node Rename → Generic LLM Nodes

Companion to `tasks.md`'s "⚠️ Correction (2026-07-11)" section and
[issue #16](https://github.com/darth-veitcher/comfydv/issues/16). This is
the properly-specced version of that deferred work — based on a full,
line-by-line inventory of every one of the ~125 affected references in
`src/comfydv/ollama.py` and `tests/test_ollama.py` (1820 lines, read in
full), not an estimate.

The inventory surfaced that this isn't one mechanical find-and-replace —
several genuine design decisions were implicit in "rename it" and needed
resolving before any code changes. Those decisions are below, followed by
the sequenced task list that implements them.

## Resolved decisions

### D1 — Single source of truth for HTTP/cache infra

`comfydv._llm.ollama_provider` owns `_post_json`, `_run_async`,
`_fetch_models`, `_TTLLRUCache`, `_cache_key`, `_MODEL_LIST_CACHE` (already
ported there — see `ollama_provider.py`). `ollama.py` stops defining its
own copies of these. The one remaining non-node use case —
`_load_default_models()` (combo-widget population at import time, before
any `OllamaClient` node exists) and the `/dv/ollama/models` refresh route —
imports `_fetch_models`/`_run_async` from `comfydv._llm.ollama_provider`
instead of duplicating them. `_CHAT_RESPONSE_CACHE` and `_post_json`
disappear from `ollama.py` entirely — nothing there needs them once
load/unload/chat delegate to `client.*`.

**Why not keep two copies:** they were already flagged as byte-identical by
the inventory (§2.13) — the only reason `ollama.py` still has them is that
nothing has repointed the imports yet. Keeping a second copy "just in case"
is exactly the kind of duplication ADR-007 exists to eliminate.

### D2 — `client == "<host string>"` equality is removed, not preserved

`OllamaProvider` is a plain object, not a `str` subclass — this is a
deliberate consequence of the adapter boundary (ADR-007), not an oversight
to work around. Two tests assert string equality on `client`
(`test_client_outputs_ollama_client_type:208-209`,
`test_client_carries_headers:1233-1234`) — both get rewritten to assert
`client.host == "..."` and `isinstance(client, OllamaProvider)`.
`OllamaClientType` (the `str`-subclass, `ollama.py:97-109`) is left in
place but becomes unused by `OllamaClient.create_client()` — not deleted in
this cutover (no test depends on deleting it, and removing a class nothing
references is a separate, lower-risk cleanup, not part of this bullet's
scope).

### D3 — Bare-string `client` backward compatibility is removed

`test_plain_string_client_has_no_headers` (`test_ollama.py:1328-1344`)
documents and tests that wiring a plain `STRING` node directly into
`client` (skipping `OllamaClient` entirely) silently works, because
`f"{client}/..."` succeeds on any string. This was never a documented,
intended feature — it's a side effect of `OllamaClientType` being a `str`
subclass, not mentioned in ADR-005 or the original Ollama epic's spec. Once
node methods call `client.chat(...)`/`client.load_model(...)`, a bare
string raises `AttributeError`. **This test is deleted**, not rewritten —
its premise (bare-string clients are supported) is being intentionally
removed, and asserting the new failure mode would just be testing that
Python raises `AttributeError` on missing methods, which isn't
comfydv-specific behavior worth a test.

The same bare-string pattern appears incidentally in ~8 other tests
(`ollama_host` fixture returns a plain string, used as `client=ollama_host`
in several integration tests — `test_ollama.py:220, 386, 407, 588, ...`).
These need `client=OllamaClient().create_client(ollama_host)[0]` instead of
`client=ollama_host` — a required edit, not optional, since they'll raise
`AttributeError` otherwise. See task T-CUT-08 below.

### D4 — Test layer split (resolves all 35 relocated `_post_json` monkeypatches)

This is the biggest structural decision. Today, `test_ollama.py` tests
ComfyUI node behavior by mocking `aiohttp` at the `ollama_mod._post_json`
seam and asserting on the exact Ollama wire payload (`keep_alive`,
`/api/generate`, tool-calling JSON shape, retry counts) *through* the node.
That seam moves — nodes no longer call `_post_json` directly, they call
`client.chat(...)` etc. Two options: (a) keep patching at whatever the new
seam is, 1:1 per test, or (b) recognize this is an architectural boundary
and split coverage accordingly. Going with **(b)**:

- **`tests/test_ollama.py`** — ComfyUI node **contract + delegation** only.
  A new `_FakeProvider` test double (implements `list_models`/
  `load_model`/`unload_model`/`chat`/`chat_structured`, records calls made
  to it) stands in for `client`. Tests assert: right method called, right
  arguments passed, return value flows through to the node's output tuple
  correctly. **No `aiohttp`/`_post_json` mocking at this layer anymore.**
  This directly matches the protocol contract's own rule ("generic nodes
  MUST NOT branch on which concrete provider type they received") — if the
  node tests don't need to know Ollama's wire format, they shouldn't mock
  it either.
- **`tests/test_ollama_provider.py`** (new file) — `OllamaProvider`'s
  actual Ollama-wire-protocol behavior: `/api/generate`+`keep_alive` int
  shape, `/api/tags` parsing into `ModelInfo`, header/timeout forwarding,
  response caching, cache-key composition. This is where the *substance* of
  today's 35 `_post_json` monkeypatches lands — not 1:1, since several
  collapse or move (see D5).
- **`tests/test_llm_chat_structured.py`** (exists, unchanged) — already
  covers the shared retry/validation/error-contract mechanism.

### D5 — Structured-output retry tests are not ported 1:1

`TestStructuredOutput` has 15 tests monkeypatching `_post_json` to assert
exact retry-count behavior (`test_retries_on_invalid_json_then_succeeds`,
`test_exhausts_retries_raises_runtime_error`, `test_max_retries_clamped_*`,
etc.). Once `OllamaProvider.chat_structured()` delegates to the already-
tested shared `chat_structured()` helper (`src/comfydv/_llm/chat.py`,
covered by `tests/test_llm_chat_structured.py`'s 6 tests), re-asserting
retry counts at the Ollama-node layer duplicates that coverage without
adding confidence. Replaced with:
- A handful of `test_ollama.py` delegation tests: `ChatCompletion` with
  `structured_output=True` calls `client.chat_structured(model, messages,
  schema, ...)` with the right schema/model/messages.
- One `test_ollama_provider.py` test: `OllamaProvider.chat_structured()`
  builds `base_url=f"{self.host}/v1"` and forwards to the shared helper
  with the right arguments.
- `test_structured_output_true_sends_tool_call_payload` (asserts the exact
  `tools`/`tool_choice` JSON shape) is **deleted** — that's `pydantic-ai`'s
  internal tool-calling mechanism now, not comfydv's; asserting on a
  third-party library's internals isn't a test worth keeping.
- Pure schema-parsing tests that don't touch HTTP at all (`_parse_output_schema`
  fail-fast checks, `_coerce_structured_value`, dynamic-socket
  `RETURN_TYPES` mutation) are unaffected — they test code that stays in
  `ollama.py` unchanged, only need the class-name rename.

### D6 — `_client_headers()` is deleted

Dead code once `OllamaLoadModel`/`OllamaUnloadModel`/`OllamaChatCompletion`
delegate to `client.*` (headers become internal to `OllamaProvider`,
captured once at construction). No test calls it directly.

### D7 — Contract doc gets a small fix

`contracts/llm_provider_protocol.md`'s illustrative code sample is missing
`timeout_secs` on `chat()`/`chat_structured()` — the actual `provider.py`
(built after the doc) has it. Fix the doc to match the real protocol; docs
follow code here, not the reverse.

### D8 — `conftest.py`'s `_clear_ollama_caches` fixture repoints

Per D1, there's now one cache source (`comfydv._llm.ollama_provider`).
Fixture imports `_CHAT_RESPONSE_CACHE`/`_MODEL_LIST_CACHE` from there
instead of `comfydv.ollama`, and `ChatCompletion` instead of
`OllamaChatCompletion`. This is the single highest-priority fixture change
— every `TestResponseCache` test (12) and every `structured_output`-
toggling test depends on it for isolation.

## Sequenced task list

Replaces `tasks.md`'s Phase 3 (US1) + Phase 5 (US3) + the deferred T014.
One coordinated PR/session, ordered so the codebase stays important at each
step even though it can't be split across separate merges (per the
2026-07-11 correction — this is genuinely atomic).

1. **T-CUT-01** — `ollama.py`: add `from comfydv._llm.ollama_provider import OllamaProvider, _fetch_models, _run_async` (drop the local `_post_json`, `_TTLLRUCache`, `_cache_key`, `_MODEL_LIST_CACHE`, `_CHAT_RESPONSE_CACHE`, `_run_async`, `_fetch_models`, `_post_json` definitions — lines 42-194 collapse to the import). Repoint `_load_default_models()` and the `/dv/ollama/models` route to the imported `_fetch_models`. (D1)
2. **T-CUT-02** — `ollama_provider.py`: implement `OllamaProvider.list_models()` (port `_fetch_models`'s `/api/tags` logic, map to `ModelInfo`/`ModelStatus.UNLOADED`/`LOADED` — Ollama never emits `SLEEPING`/`DOWNLOADING`, per ADR-007's documented approximation), `load_model()` (port `/api/generate` + `keep_alive: -1`), `unload_model()` (port `/api/generate` + `keep_alive: 0`), `chat()` (port native `/api/chat` non-structured path), `chat_structured()` (build `base_url=f"{self.host}/v1"`, delegate to `comfydv._llm.chat.chat_structured()`).
3. **T-CUT-03** — `tests/test_ollama_provider.py` (new): tests for T-CUT-02's method bodies, mocking at `ollama_provider_mod._post_json`/`aiohttp.ClientSession` — ports the *substance* of the 35 relocated monkeypatches per D4/D5 (not 1:1 — collapses redundant retry-count tests per D5).
4. **T-CUT-04** — `ollama.py`: `OllamaClient.RETURN_TYPES = ("LLM_CLIENT",)`, `create_client()` returns `OllamaProvider(host, headers)`. (D2)
5. **T-CUT-05** — `ollama.py`: rename `OllamaModelSelector`→`LLMModelSelector`, `OllamaLoadModel`→`LLMLoadModel`, `OllamaUnloadModel`→`LLMUnloadModel`, `OllamaChatCompletion`→`ChatCompletion`; every `"OLLAMA_CLIENT"` input socket → `"LLM_CLIENT"`; rewrite the 3 method bodies (`load_model`, `unload_model`, `chat`) to delegate to `client.*` instead of `_post_json`/f-string URLs; delete `_client_headers` (D6); update the 3 `OllamaChatCompletion.*` references in the `/dv/ollama/update_structured_outputs` route body.
6. **T-CUT-06** — `src/comfydv/__init__.py`: update imports and `NODE_CLASS_MAPPINGS`/`NODE_DISPLAY_NAME_MAPPINGS` for the 4 renamed classes.
7. **T-CUT-07** — `tests/conftest.py`: repoint `_clear_ollama_caches` (D8) and `first_generative_model`'s `_fetch_models` import (D1).
8. **T-CUT-08** — `tests/test_ollama.py`: update the import block (4 class renames); add `_FakeProvider` test double; convert every `_post_json`-monkeypatched test to use `_FakeProvider` as `client` instead (D4); replace bare-string `client=ollama_host`/`client="http://..."` usages with a constructed provider (D3); rewrite the 2 `client == "<string>"` assertions (D2); delete `test_plain_string_client_has_no_headers` (D3) and `test_structured_output_true_sends_tool_call_payload` (D5); collapse the 15 `TestStructuredOutput` retry-count tests per D5; update `TestNodeContracts`'s `NODE_CLASSES` list (4 renames).
9. **T-CUT-09** — `contracts/llm_provider_protocol.md`: add missing `timeout_secs` params (D7).
10. **T-CUT-10** — Full suite green (`uv run pytest -m "not integration and not system"`), `ruff check --fix && ruff format`, `ty check`, `beacon doctor --strict`.
11. **T-CUT-11** — `tasks.md`: mark T007-T010/T015-T018/T014 done, referencing this plan; migration mapping (old→new names, FR-009) as a module-level constant/docstring in `ollama.py`.
12. **T-CUT-12** — Manual smoke test against a live local Ollama server per `quickstart.md`.

## What stays exactly as originally scoped

`OllamaHeader*`, `OllamaOption*`, `OllamaDebugHistory`, `OllamaHistoryLength`
classes and the `OLLAMA_HEADERS`/`OLLAMA_OPTIONS`/`OLLAMA_HISTORY` socket
types are **out of scope** — confirmed zero test dependencies force a
change, and ADR-007 never proposed touching them (only the
model-management/chat surface generalizes). `_parse_output_schema`,
`_comfy_types_for_schema`, `_build_structured_model`,
`_coerce_structured_value` stay in `ollama.py` unchanged — pure/local
schema logic with no network dependency, still needed by the live-preview
route.
