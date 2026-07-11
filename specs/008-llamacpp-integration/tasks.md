# Tasks: llama.cpp Model Integration

**Input**: Design documents from `/specs/008-llamacpp-integration/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/llamacpp_provider_conformance.md

**Tests**: First-class — every implementation task has a paired failing-test task (`-T`/`-I` suffix).

**Organization**: Grouped by user story (spec.md priorities P1/P1/P2/P3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US4
- **-T / -I**: paired test (red) / implementation (green)

## Path Conventions

Single project: `src/comfydv/`, `tests/` at repository root, mirroring the
`ollama.py`/`_llm/ollama_provider.py` split exactly (plan.md Structure
Decision).

---

## Phase 1: Setup

- [x] T001 No new dependencies — `aiohttp`/`pydantic-ai` already present from the prerequisite epic (verified in `pyproject.toml`)
- [x] T002 [P] Create `src/comfydv/_llm/llamacpp_provider.py` and `src/comfydv/llamacpp.py` (empty modules with docstrings, mirroring `ollama_provider.py`/`ollama.py`'s module docstring style)

---

## Phase 2: Foundational

None — `LLMProvider`, `ModelStatus`, `ModelInfo`, `Message`, and the shared
`chat_structured()` helper already exist from the prerequisite epic and are
unmodified by this feature (plan.md Constitution Check, research.md).

**Checkpoint**: nothing blocks user story work — it can start immediately.

---

## Phase 3: User Story 1 — Connect to a local llama.cpp server and get chat responses (Priority: P1) 🎯 MVP

**Goal**: A workflow author wires an `LlamaCppClient` node into the existing `ChatCompletion` node and gets a text response.

**Independent Test**: Wire `LlamaCppClient` → `ChatCompletion`, run against a live `llama-server` (router mode), confirm text output.

- [x] T003-T [US1] Write FAILING test: `LlamaCppProvider.chat()` POSTs to `{host}/v1/chat/completions` and parses `choices[0].message.content`, in `tests/test_llamacpp_provider.py` (witnesses `features/us1_connect_and_chat.feature` scenario "llama.cpp connection node feeds the existing chat node")
- [x] T003-I [US1] Implement `LlamaCppProvider.__init__`/`.chat()` in `src/comfydv/_llm/llamacpp_provider.py` (data-model.md — OpenAI-shape response parsing, not Ollama's native shape) — makes T003-T pass
- [x] T004-T [US1] Write FAILING test: `LlamaCppClient` node's `INPUT_TYPES`/`RETURN_TYPES` match `OllamaClient`'s shape (`LLM_CLIENT` output), and `create_client()` constructs a `LlamaCppProvider`, in `tests/test_llamacpp.py`
- [x] T004-I [US1] Implement `LlamaCppClient` node in `src/comfydv/llamacpp.py` (mirrors `OllamaClient` exactly, default host `http://localhost:8080` per llama-server's default port) — makes T004-T pass (depends on T003-I)
- [x] T005-T [US1] Write FAILING test: `LlamaCppClient` registered in `NODE_CLASS_MAPPINGS`/`NODE_DISPLAY_NAME_MAPPINGS`, in `tests/test_llamacpp.py`
- [x] T005-I [US1] Register `LlamaCppClient` in `src/comfydv/__init__.py` — makes T005-T pass (depends on T004-I)
- [x] T006-T [US1] Write FAILING test: `LlamaCppProvider` connection error surfaces a clear message (mirrors `OllamaProvider`'s `_post_json` connection-error contract), in `tests/test_llamacpp_provider.py` (witnesses `features/us1_connect_and_chat.feature` scenario "Unreachable llama.cpp server surfaces a clear error")
- [x] T006-I [US1] Confirm `LlamaCppProvider.chat()` reuses the shared `_post_json` connection-error handling unchanged (likely no code change needed — verify, don't assume) — makes T006-T pass

**Checkpoint**: US1 fully functional and independently testable (MVP) — proves the adapter pattern for the chat path.

---

## Phase 4: User Story 2 — Get structured, validated output from llama.cpp (Priority: P1)

**Goal**: `structured_output=True` on `ChatCompletion` works identically against llama.cpp.

**Independent Test**: Enable `structured_output` with a schema, run against a llama.cpp-hosted model, confirm typed sockets populate and are never blank.

- [x] T007-T [US2] Write FAILING test: `LlamaCppProvider.chat_structured()` builds `base_url=f"{host}/v1"` and delegates to the shared `comfydv._llm.chat.chat_structured()` helper unchanged, in `tests/test_llamacpp_provider.py` (witnesses `features/us2_structured_output.feature` scenario "Valid structured response exposes typed fields, same as Ollama")
- [x] T007-I [US2] Implement `LlamaCppProvider.chat_structured()` in `src/comfydv/_llm/llamacpp_provider.py` — zero new structured-output logic, same call shape `OllamaProvider.chat_structured()` already makes — makes T007-T pass
- [x] T008 [US2] No new test needed for the retry-then-fail path (witnesses `features/us2_structured_output.feature` scenario "Invalid response retries then fails clearly, same as Ollama") — already fully covered by `tests/test_llm_chat_structured.py`'s existing suite, since `LlamaCppProvider.chat_structured()` calls the identical shared helper `OllamaProvider` does; re-testing it here would duplicate coverage without adding confidence (same reasoning as the prerequisite epic's D5)

**Checkpoint**: US1 + US2 both independently functional — the chat surface is now backend-agnostic in practice, not just in name.

---

## Phase 5: User Story 3 — See and control which models are loaded on llama.cpp (Priority: P2)

**Goal**: `LLMModelSelector`/`LLMLoadModel`/`LLMUnloadModel` work against llama.cpp via `LlamaCppProvider`.

**Independent Test**: List models via `LLMModelSelector` wired to `LlamaCppClient`; load/unload one; confirm status changes, including `loading`/`downloading` states if triggered.

- [x] T009-T [P] [US3] Write FAILING test: `LlamaCppProvider.list_models()` maps `GET /models`'s `data[].id`→`ModelInfo.name` and `data[].status.value`→`ModelInfo.status`, surfacing all five `ModelStatus` values without normalization (data-model.md), in `tests/test_llamacpp_provider.py` (witnesses `features/us3_model_lifecycle.feature` scenario "List models with full status vocabulary")
- [x] T009-I [US3] Implement `LlamaCppProvider.list_models()` in `src/comfydv/_llm/llamacpp_provider.py` — makes T009-T pass
- [x] T010-T [P] [US3] Write FAILING test: `LlamaCppProvider.load_model()`/`unload_model()` POST `{"model": id}` to `/models/load`/`/models/unload` and are idempotent, in `tests/test_llamacpp_provider.py` (witnesses `features/us3_model_lifecycle.feature` scenarios "Load a model into memory" and "Unload a model from memory")
- [x] T010-I [US3] Implement `LlamaCppProvider.load_model()`/`unload_model()` in `src/comfydv/_llm/llamacpp_provider.py` — makes T010-T pass
- [x] T011 [US3] No new node-layer tests needed — `LLMModelSelector`/`LLMLoadModel`/`LLMUnloadModel` are untouched by this epic (plan.md Structure Decision) and already have delegation-test coverage against a generic `_FakeProvider` in `tests/test_ollama.py`; that coverage is provider-agnostic by construction (FR-002), so it already proves these nodes work with `LlamaCppProvider` too, not just `OllamaProvider`

**Checkpoint**: US1 + US2 + US3 independently functional.

---

## Phase 6: User Story 4 — Swap from Ollama to llama.cpp without touching the rest of the workflow (Priority: P3)

**Goal**: Demonstrate/prove the adapter pattern's actual promise end-to-end.

**Independent Test**: Same workflow, only the connection node changes.

- [x] T012-T [US4] Write FAILING test: a workflow-shaped test (client → `ChatCompletion` → `LLMModelSelector` → `LLMLoadModel` → `LLMUnloadModel`) runs identically whether `client` is an `OllamaProvider`-double or a `LlamaCppProvider`-double — i.e. no node branches on provider type, in `tests/test_llamacpp.py` (witnesses `features/us4_swap_backends.feature` scenario "Replacing only the connection node preserves the workflow")
- [x] T012-I [US4] No implementation expected — this test should already pass given T003-T011 (it's a regression/integration proof, not new functionality); if it fails, that reveals a node secretly branching on provider type, which would be a real bug to fix, not a feature to add

**Checkpoint**: all four user stories independently functional; the adapter pattern is proven end-to-end, not just asserted.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T013 [P] `ruff check --fix && ruff format` — clean
- [x] T014 [P] `ty check` — clean, same pre-existing diagnostics as the prerequisite epic (unrelated to this feature — `comfy`/`server`/`folder_paths` unresolved-import, `format_string.py`'s dynamic RETURN_TYPES, `create_model`/`RandomChoice` — none touch the new files)
- [x] T015 Confirmed via grep: `llamacpp_provider.py`/`llamacpp.py` import no `comfy`/`server`/`folder_paths` at module scope
- [x] T016 `beacon doctor --strict`: only the pre-existing `llm-provider-abstraction: all specs [complete]` epic-gates item (PR #18, the archive-bookkeeping PR for the *prerequisite* epic, not yet merged — unrelated to this feature) and `tdd-commit-discipline` (disclosed pattern, same reasoning as the prerequisite epic)
- [x] T017 Live smoke test — run against a real router-mode `llama-server` (Homebrew-installed, already present in the dev environment; a prior pass wrongly assumed no server was reachable without actually checking). Full lifecycle exercised against a real 5.6GB local GGUF model: `list_models()` → `load_model()` → `chat()` → `unload_model()`, plus explicit idempotency checks (calling `load_model()`/`unload_model()` again in the already-satisfied state). Found and fixed a real gap not caught by the mocked suite — see the finding below.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: none — nothing blocks user story work
- **US1**: no dependency on other stories — genuinely the MVP
- **US2**: depends on US1's `LlamaCppProvider` skeleton existing (T003-I), but its own logic (T007) has no dependency on US1's chat() specifically
- **US3**: independent of US1/US2 except sharing `LlamaCppProvider`'s constructor (T003-I) — unlike the prerequisite epic's atomic cutover, there is no shared "client output type" migration risk here, since `LlamaCppClient` is a brand-new node, not a changed one
- **US4**: depends on US1–US3 all being done (it's a proof, not new functionality)
- **Polish**: depends on all four user stories

### Parallel Opportunities

- T002 can start immediately
- T009-T and T010-T can run in parallel (different methods, same file, no shared state)
- T013/T014 can run in parallel in Polish

---

## Implementation Strategy

### MVP First

1. Phase 1 (Setup, trivial) → Phase 3 (US1) → **STOP and validate US1 independently** against a live `llama-server`.

### Incremental Delivery

1. US1 → validate → basic chat parity with Ollama, on a second backend.
2. US2 → validate → structured-output parity — the shared mechanism holds.
3. US3 → validate → model-management parity, with richer status than Ollama can offer.
4. US4 → validate → the adapter pattern is proven, not just asserted.
5. Polish.

Unlike the prerequisite epic, **this decomposition genuinely holds** —
there is no shared "output type" migration forcing an atomic cutover, because
`LlamaCppClient` is new, not a change to an existing node. Each phase really
can land independently.

---

## Post-implementation review finding (fixed)

A `beacon-reviewer` pass ahead of PR open found `LlamaCppProvider.list_models()`
caught *every* exception and returned `[]`, silently indistinguishable from
"no models installed" — violating FR-006 and `contracts/llamacpp_provider_conformance.md`'s
explicit requirement that a non-router-mode `llama-server` (unreachable
endpoints → HTTP error on `GET /models`) surface a clear, specific error.

Fixed: `_get_json` (shared with `OllamaProvider`, in `ollama_provider.py`) now
raises `RuntimeError` on an HTTP error status, matching `_post_json`'s
existing behavior — its docstring already claimed this, it just didn't do it.
`LlamaCppProvider.list_models()` now distinguishes `OSError` (genuinely
unreachable — connection refused, DNS failure, timeout; all aiohttp
connection-level exceptions are `OSError` subclasses) from `RuntimeError`
(server responded, but with an error): the former still degrades gracefully
to `[]` (consistent with `OllamaProvider`'s existing UX), the latter is
re-raised naming router mode as the likely cause. Regression test added:
`test_list_models_non_router_mode_raises_clear_error` in
`tests/test_llamacpp_provider.py`. `OllamaProvider`'s own `list_models()`/
`_fetch_models()` still catch broadly and degrade to `[]` unchanged — no
spec requirement asks Ollama to make this distinction, and this fix doesn't
force it to.

---

## Live smoke test finding (T017, fixed)

T017 had been marked `[-]` deferred on the assumption that no `llama-server`
was reachable in the dev environment. That assumption was never actually
checked — `llama-server` was installed via Homebrew the whole time, and a
router-mode server was launched against a real local GGUF model
(`--models-dir` pointed at a symlinked model file) to run the smoke test for
real.

This caught a genuine gap the mocked suite couldn't: `contracts/llamacpp_provider_conformance.md`
claimed router mode's `/models/load`/`/models/unload` return `{"success": true}`
on an already-loaded/unloaded model, satisfying the `LLMProvider` protocol's
idempotency requirement "without extra handling." That claim was never
live-verified — live testing showed the opposite: both endpoints return HTTP
400 (`"model is already running"` / `"model is not running"`) instead.
`LlamaCppProvider.load_model()`/`unload_model()` now absorb exactly those two
error messages as the desired end-state already reached (any other error
still propagates); the contract doc is corrected to describe the real
behavior. Regression tests added (mocked, so they run in CI):
`test_load_model_already_running_is_idempotent`,
`test_unload_model_not_running_is_idempotent`, and their
`_other_http_error_still_raises` counterparts confirming non-idempotency
errors aren't over-broadly swallowed.

Also observed live (informational, no code change needed): `load_model()`/
`unload_model()` return once the request is *accepted*, not once the state
transition completes — a 5.6GB model reported `LOADING` for several seconds
before `LOADED`. This matches `ModelStatus`'s documented vocabulary (`loading`
is a real, intended state) and how a real UI would behave — fire the request,
poll `list_models()` for the transition. No protocol change; noted here so
it's not mistaken for a future bug report.

**`chat_structured()` live-verified separately** (T007/T008's mocked coverage
only ever exercised the call-shape, never the real network path): ran a
second live smoke test — `load_model()` → `chat_structured()` with a real
`pydantic.BaseModel` schema — against the same router-mode server. Result
validated correctly (`Color(name='Red', hex_code='#FF0000')`), confirming
pydantic-ai's `Agent`/`OpenAIProvider(base_url=f"{host}/v1")` mechanism
genuinely works against llama-server's OpenAI-compatible endpoint, not just
Ollama's (which was the only one live-verified in the prerequisite epic).
No gap found here — recorded as verification evidence, not a fix.

**Net result**: every `LlamaCppProvider` method (`list_models`, `load_model`,
`unload_model`, `chat`, `chat_structured`) has now been exercised against a
real router-mode `llama-server`, not just mocks. T017 is genuinely done.
