# Tasks: LLM Provider Abstraction

**Input**: Design documents from `/specs/007-llm-provider-abstraction/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/llm_provider_protocol.md

**Tests**: First-class (spec carries Acceptance Scenarios) — every implementation task has a paired failing-test task (`-T`/`-I` suffix) per BEACON's test-first discipline.

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P1/P2/P3) to enable independent implementation and testing of each.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- **-T / -I**: paired test (red) / implementation (green) — a `-I` task is never parallel with its own `-T`

## Path Conventions

Single project: `src/comfydv/`, `tests/` at repository root (per plan.md's Project Structure).

---

## Phase 1: Setup

- [x] T001 Add `pydantic-ai` and `openai` to `pyproject.toml` dependencies; curate the addition into `requirements.txt` per [ADR-003](../../project-management/ADRs/ADR-003-requirements-txt-authoring-policy.md)
- [x] T002 [P] Create `src/comfydv/_llm/__init__.py` (empty package init)

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 [P] Define `Message`, `ModelStatus`, `ModelInfo` in `src/comfydv/_llm/provider.py` per `data-model.md`
- [x] T004 Define the `LLMProvider` `Protocol` in `src/comfydv/_llm/provider.py` per `contracts/llm_provider_protocol.md` (depends on T003)
- [x] T005 [P] `LLM_CLIENT` is introduced as part of T007-I (`OllamaClient`'s output type) rather than as a standalone constant — ComfyUI socket types are plain string literals, not declared objects; folded in, not skipped
- [x] T006 Scaffold `OllamaProvider.__init__(self, host, headers)` in `src/comfydv/_llm/ollama_provider.py`, porting the existing module-level `_post_json`/`_fetch_models`/`_run_async`/`_TTLLRUCache` helpers from `ollama.py` into it — behavior-preserving port, not a rewrite (depends on T004)

**Checkpoint**: protocol + provider skeleton exist; user story work can begin.

---

## Phase 3: User Story 1 — Connect to a local server and get chat responses (Priority: P1) 🎯 MVP

**Goal**: A workflow author wires a client node into a generic chat node and gets a text response.

**Independent Test**: Wire `OllamaClient` → `ChatCompletion`, run against a live server, confirm text output.

**Superseded 2026-07-11 — see `atomic-cutover-plan.md`.** T007–T010 as
written below assumed US1 was independently deliverable; it isn't (see the
correction at the bottom of this file). The actual work is now
`atomic-cutover-plan.md`'s **T-CUT-04, T-CUT-05, T-CUT-06, T-CUT-08**
(`OllamaClient` output-type change, `ChatCompletion` rename+delegation,
`__init__.py` registration, and the corresponding `test_ollama.py`
rewrite using a `_FakeProvider` double). Original text kept below for
history, not as the active task list:

- [-] T007-T [US1] ~~Write FAILING test: `OllamaClient` node constructs and outputs an `OllamaProvider` via the `LLM_CLIENT` socket, in `tests/test_ollama.py`~~ _Superseded, see Phase 8 T-CUT-08._
- [-] T007-I [US1] ~~Update `OllamaClient` in `src/comfydv/ollama.py` to construct and output an `OllamaProvider` via `LLM_CLIENT`~~ _Superseded, see Phase 8 T-CUT-04._
- [-] T008-T [US1] ~~Write FAILING test: `OllamaProvider.chat()` returns model text via the existing `/api/chat` aiohttp call~~ _Superseded, see Phase 8 T-CUT-03._
- [-] T008-I [US1] ~~Implement `OllamaProvider.chat()` in `src/comfydv/_llm/ollama_provider.py`~~ _Superseded, see Phase 8 T-CUT-02._
- [-] T009-T [US1] ~~Write FAILING test: generic `ChatCompletion` node (non-structured) calls `provider.chat()` and surfaces a clear error on an unreachable host~~ _Superseded, see Phase 8 T-CUT-08._
- [-] T009-I [US1] ~~Rename `OllamaChatCompletion` → `ChatCompletion`, delegate the non-structured path to `LLMProvider.chat()`, update `NODE_CLASS_MAPPINGS`~~ _Superseded, see Phase 8 T-CUT-05/T-CUT-06._
- [-] T010-T [US1] ~~Write FAILING test: two `ChatCompletion` nodes sharing one `OllamaClient` both pick up a host change~~ _Superseded, see Phase 8 T-CUT-08._
- [-] T010-I [US1] ~~Verify/adjust that `OllamaClient` → `OllamaProvider` construction happens per node execution~~ _Superseded, folded into Phase 8 T-CUT-04 (construction is already per-call in `create_client()`)._

**Checkpoint**: superseded — see `atomic-cutover-plan.md`'s checkpoint (T-CUT-10, full suite green).

---

## Phase 4: User Story 2 — Structured, validated output (Priority: P1)

**Goal**: The chat node's `structured_output` toggle returns validated typed fields via the shared `pydantic-ai` mechanism.

**Independent Test**: Enable `structured_output` with a schema, run against a model, confirm typed sockets are populated and never blank.

- [x] T011-T [P] [US2] Write test: `chat_structured()` returns a validated schema instance on success, in `tests/test_llm_chat_structured.py` (witnesses `features/us2_structured_output.feature` scenario "Valid structured response exposes typed fields") — mocked at the `_build_agent` seam after an API-discovery spike into pydantic-ai's exact `Agent`/`OpenAIProvider`/`OpenAIChatModel` constructor and exception surface (not guessable from training data alone — verified live against the installed package); tests and implementation validated together rather than strictly red-first, noted honestly rather than presented as pure TDD
- [x] T011-I [US2] Implement the shared `chat_structured()` helper in `src/comfydv/_llm/chat.py` using `pydantic-ai`'s `Agent`/`output_type` through `OpenAIProvider(base_url=<host>/v1)` + `OpenAIChatModel` — makes T011-T pass (depends on T004)
- [x] T012-T [US2] Write test: invalid/failed-validation responses trigger automatic retry up to `max_retries` (clamped 0–5), in `tests/test_llm_chat_structured.py` (witnesses `features/us2_structured_output.feature` scenario "Invalid response triggers automatic retry")
- [x] T012-I [US2] Implement the bounded retry loop (0–5, matching ADR-006's existing contract) around the `pydantic-ai` call in `src/comfydv/_llm/chat.py`, with the Agent's own internal retries disabled (`retries=0`) so the error contract is comfydv's — makes T012-T pass (depends on T011-I)
- [x] T013-T [US2] Write test: exhausted retries raise `RuntimeError` naming the model, attempt count, and a truncated last-response snippet, in `tests/test_llm_chat_structured.py` (witnesses `features/us2_structured_output.feature` scenario "Exhausted retries fail clearly instead of passing through bad data")
- [x] T013-I [US2] Implement the exhausted-retry error path in `src/comfydv/_llm/chat.py`, matching ADR-006's existing error message contract (model, attempt count, truncated last response) — makes T013-T pass (depends on T012-I)
- [-] T014-T [US2] _Superseded — see `atomic-cutover-plan.md` D5 and T-CUT-08. Original: write FAILING test that `ChatCompletion`'s `structured_output=True` path wires a schema through `chat_structured()` to per-field dynamic ComfyUI output sockets. D5 replaces the originally-planned retry-count-style test with a delegation test against a `_FakeProvider`, since retry behavior is already covered by `tests/test_llm_chat_structured.py`._
- [-] T014-I [US2] _Superseded — see `atomic-cutover-plan.md` T-CUT-05. Original: wire `ChatCompletion`'s `structured_output`/`output_schema` inputs to `LLMProvider.chat_structured()`, preserving the dynamic-socket UX from ADR-006 — still the right implementation shape, just executed as part of the coordinated T-CUT-05 rename, not standalone._

**Checkpoint**: US1 + US2 both independently functional — matches today's Ollama capability, now on the shared mechanism.

---

## Phase 5: User Story 3 — Manage model residency (Priority: P2)

**Goal**: List/load/unload models through generic nodes against any connected provider.

**Independent Test**: List models via `LLMModelSelector`; load/unload one via `LLMLoadModel`/`LLMUnloadModel`; confirm status changes.

**Superseded 2026-07-11 — see `atomic-cutover-plan.md`.** Maps to
**T-CUT-02** (`OllamaProvider.list_models`/`load_model`/`unload_model`
method bodies), **T-CUT-03** (`tests/test_ollama_provider.py`, new file),
and **T-CUT-05/T-CUT-06/T-CUT-08** (the node renames + delegation +
registration + test rewrite). Original text kept for history:

- [-] T015-T [US3] ~~Write FAILING test: `OllamaProvider.list_models()` returns `ModelInfo` entries with status normalized into `ModelStatus`~~ _Superseded, see Phase 8 T-CUT-03._
- [-] T015-I [US3] ~~Implement `OllamaProvider.list_models()`~~ _Superseded, see Phase 8 T-CUT-02._
- [-] T016-T [US3] ~~Write FAILING test: `OllamaProvider.load_model()`/`unload_model()` are idempotent~~ _Superseded, see Phase 8 T-CUT-03._
- [-] T016-I [US3] ~~Implement `OllamaProvider.load_model()`/`unload_model()`~~ _Superseded, see Phase 8 T-CUT-02._
- [-] T017-T [US3] ~~Write FAILING test: generic `LLMModelSelector` node returns model+status pairs~~ _Superseded, see Phase 8 T-CUT-08._
- [-] T017-I [US3] ~~Rename `OllamaModelSelector` → `LLMModelSelector`, delegate to `LLMProvider.list_models()`~~ _Superseded, see Phase 8 T-CUT-05/T-CUT-06._
- [-] T018-T [US3] ~~Write FAILING test: generic `LLMLoadModel`/`LLMUnloadModel` nodes call the protocol~~ _Superseded, see Phase 8 T-CUT-08._
- [-] T018-I [US3] ~~Rename `OllamaLoadModel`/`OllamaUnloadModel` → `LLMLoadModel`/`LLMUnloadModel`~~ _Superseded, see Phase 8 T-CUT-05/T-CUT-06._

**Checkpoint**: superseded — see `atomic-cutover-plan.md`.

---

## Phase 6: User Story 4 — Reconnect an existing workflow after upgrading (Priority: P3)

**Goal**: A clear old→new node mapping exists, and migrated workflows are output-equivalent.

**Independent Test**: Follow the mapping to reconnect a pre-upgrade workflow; confirm equivalent output.

- [-] T019 [US4] ~~Add a migration mapping constant~~ _Superseded, see Phase 8 T-CUT-11._
- [-] T020 [US4] ~~Full suite green, SC-003 equivalence~~ _Superseded, see Phase 8 T-CUT-10._
- [-] T021 [US4] ~~Update quickstart.md migration section~~ _Superseded, see Phase 8 T-CUT-12._

**Checkpoint**: all four user stories independently functional; migration path documented.

---

## Phase 8: Atomic Node Cutover (supersedes Phases 3, 5, and T014/T019-T021)

**Goal**: execute `atomic-cutover-plan.md`'s 12-step sequenced plan as one
coordinated change — this is the actual current work; Phases 3/5's `[-]`
entries above are historical only.

**Not TDD-paired** the way earlier phases are — per the correction above,
this genuinely can't be decomposed into independent red/green pairs (a
class rename fails test *collection* for the whole file at once). Each
T-CUT step is still verified incrementally during implementation; the
suite only needs to be green as a whole at T-CUT-10, not after every step.

- [x] T-CUT-01 [P] `ollama.py`: import HTTP/cache infra from `comfydv._llm.ollama_provider` instead of duplicating it; repoint `_load_default_models()`/`/dv/ollama/models` route (plan D1)
- [x] T-CUT-02 `ollama_provider.py`: implement `OllamaProvider.list_models()`/`load_model()`/`unload_model()`/`chat()`/`chat_structured()` method bodies (ports existing inline logic; `chat_structured()` delegates to `_llm/chat.py`; `list_models()` also queries `/api/ps` to distinguish loaded/unloaded, a genuinely new capability the old `OllamaModelSelector` never had)
- [x] T-CUT-03 `tests/test_ollama_provider.py` (new file): tests for T-CUT-02, mocking at the `ollama_provider` seam (plan D4/D5)
- [x] T-CUT-04 `ollama.py`: `OllamaClient.RETURN_TYPES` → `("LLM_CLIENT",)`, `create_client()` returns `OllamaProvider(host, headers)` (plan D2)
- [x] T-CUT-05 `ollama.py`: rename the 4 classes, `"OLLAMA_CLIENT"`→`"LLM_CLIENT"` on every consumer, rewrite the 3 delegating method bodies, delete `_client_headers` (plan D6)
- [x] T-CUT-06 `src/comfydv/__init__.py`: update imports and `NODE_CLASS_MAPPINGS`/`NODE_DISPLAY_NAME_MAPPINGS`
- [x] T-CUT-07 `tests/conftest.py`: repoint `_clear_ollama_caches` and `first_generative_model`'s `_fetch_models` import (plan D8) — `first_generative_model`'s import needed no change (still re-exported from `comfydv.ollama`)
- [x] T-CUT-08 `tests/test_ollama.py`: rewrote against a `_FakeProvider` double per plan D4/D5 — 98 unit tests, all passing. Also fixed a real gap the rename surfaced: `comfy-manager-entry.json`'s `nodename` list (and its matching test expectation) still had the old display names — updated both.
- [x] T-CUT-09 [P] `contracts/llm_provider_protocol.md`: `timeout_secs` fix (commit `ef2464a`)
- [x] T-CUT-10 Full suite green (218 passed, only the pre-existing unrelated Dockerfile-python-version test fails), `ruff check --fix && ruff format` clean, `ty check` clean (confirmed the `create_model`/`RandomChoice` diagnostics pre-date this cutover via `git stash` comparison), `beacon doctor --strict` shows only pre-existing/disclosed items (`tdd-commit-discipline` — already documented as an intentional deviation; `epic-gates` — `llamacpp-integration` correctly has no specs yet)
- [x] T-CUT-11 [P] `tasks.md`/`ollama.py`: migration mapping constant (FR-009) — `MIGRATION_MAP` dict, `ollama.py`
- [x] T-CUT-12 [P] Ollama was reachable in this environment — ran the real `@pytest.mark.integration` suite (not just a manual walkthrough). 6/8 passed, including the critical ones: unreachable-host error handling, real load/unload against the live server, structured-output retry-then-raise against the live server, temperature-determinism. 2 failures (`test_single_turn_returns_non_empty_response`, `test_multi_turn_receives_context`) — confirmed via direct `curl` to `/api/chat` (bypassing this codebase entirely) that the test model (`lukey03/qwen3.5-9b-abliterated-vision`) itself returns a degenerate empty response server-side; this is the exact pre-existing model unreliability ADR-006 already documented, not a cutover regression.

**Checkpoint**: T-CUT-10 green = all four user stories functional on the generic nodes; T-CUT-11/12 close out US4.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T022 [P] Run `uv run ruff check --fix && uv run ruff format` across `src/comfydv/_llm/`, `tests/test_ollama_provider.py`, and the modified `ollama.py`/`__init__.py`
- [ ] T023 [P] Run `uv run ty check` and resolve any typing errors introduced by the `LLMProvider` `Protocol`
- [ ] T024 Confirm Constitution Principle IV: `src/comfydv/_llm/` imports no `comfy`/`server` at module scope (guarded, matching `ollama.py`'s existing pattern)
- [ ] T025 Run `beacon doctor --strict` and resolve any findings, including `spec-bdd-coverage` and `tdd-commit-discipline` for this spec
- [ ] T026 Walk `quickstart.md` end-to-end manually against a live local server to confirm the documented flow works as written

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories
- **User Stories (Phase 3–6)**: all depend on Foundational; US1 has no dependency on US2/US3/US4; US2's `ChatCompletion` wiring (T014) depends on US1's node rename (T009-I); US3 is independent of US1/US2 except for sharing `OllamaProvider`'s constructor (T006); US4 depends on the node renames done in US1/US3 (T009-I, T017-I, T018-I) since it documents them
- **Polish (Phase 7)**: depends on all four user stories

### Parallel Opportunities

- T002 (package init) can run alongside T001 (dependency addition)
- T003 and T005 can run in parallel (different files/concerns) within Foundational
- T008-T (provider-level test) can run in parallel with T007-T (node-level test) — different files
- T011-T, T015-T, T016-T can each start as soon as Foundational is done, in parallel with US1 — different files, no shared dependency beyond T004/T006
- T022/T023 (lint/type-check) can run in parallel in Polish

---

## Implementation Strategy

### MVP First

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1) → **STOP and validate US1 independently** against a live local server.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → validate → this alone restores basic chat parity with today's Ollama integration, on the new mechanism.
3. US2 → validate → restores structured-output parity (the ADR-006→ADR-007 migration is now complete in behavior).
4. US3 → validate → restores model-management parity.
5. US4 → validate → migration guidance ships; full regression pass (T020) confirms SC-003.
6. Polish.

Each story adds value without breaking the previous one — this mirrors the epic's own framing: US1+US2 together are the risky "prove the migration is behavior-preserving" core; US3 and US4 round out parity and upgrade experience.

---

## ⚠️ Correction (2026-07-11) — US1/US3 independence claim was wrong

**Discovered mid-implementation, confirmed by independent product + engineering
review (agent-trio deliberation, aligned verdicts):** the "US1 has no
dependency on other stories" and "US3 is independent of US1/US2" claims above
are **false**. `OllamaClient` is a single shared producer node — every
downstream node (`OllamaModelSelector`, `OllamaLoadModel`,
`OllamaUnloadModel`, `OllamaChatCompletion`) consumes its output via
`f"{client}/api/..."` string interpolation (10 call sites in `ollama.py`).
Changing `OllamaClient` to emit an `OllamaProvider` object instead of the
current string-like `OllamaClientType` breaks **all four** consumers
simultaneously — there is no way to migrate just `ChatCompletion` (US1)
while leaving `OllamaModelSelector`/`OllamaLoadModel`/`OllamaUnloadModel`
(US3) on the old string-based access pattern. Separately, renaming these
classes breaks `tests/test_ollama.py`'s imports atomically (125 references
across the file) — a class rename fails test *collection* for the whole
file at once, not test-by-test.

**Rejected fix:** making `OllamaProvider` also subclass `str` (mirroring
`OllamaClientType`'s trick) to preserve incremental per-node migration.
Both reviewers rejected this — it reintroduces the exact hack ADR-007
exists to eliminate into the new clean boundary, and would silently mask an
incomplete cutover (un-migrated consumers keep working via the string
trick, so T020's regression pass would go green for the wrong reason).

**Decision:** T007–T010 (US1) and T015–T018 (US3)'s *node-layer* work
(everything that touches `OllamaClient`'s output type or renames a node
class) must land as **one atomic cutover** — one coordinated change across
`ollama.py` and `tests/test_ollama.py`, verified green as a whole, not as
separable per-story TDD pairs. This is sized beyond a single 2–4h tracer
bullet and is explicitly re-scoped as its own dedicated BUILD session
(tracked in GitHub issue — see epic Notes for the link once filed), not
attempted in the same session as the Foundational layer (T001–T006, already
shipped safely — see git log). The *provider-layer* work that doesn't touch
`ollama.py` (e.g. `OllamaProvider.chat()`/`list_models()`/`load_model()`/
`unload_model()` method bodies, and the `pydantic-ai`-backed
`chat_structured()` helper) remains genuinely independent and safe to build
ahead of the cutover — only the ComfyUI node-layer rename is atomic.

ADR-007's own decision (breaking rename, no deprecated aliases) is
**unaffected** — that call was about user-facing blast radius (small,
Ollama integration shipped 2026-07-04), which this finding doesn't change.
What's re-scoped is delivery sequencing, not the design decision.

---

## ✅ Properly specced (2026-07-11) — see `atomic-cutover-plan.md`

Full line-by-line inventory of every affected reference in `ollama.py` and
`tests/test_ollama.py` (1820 lines, read in full), the design decisions it
surfaced (cache-singleton duplication, `client == "<string>"` equality
breaking, bare-string-client backward compat removal, and — the big one —
a test-layer split so the 35 relocated `_post_json` monkeypatches land at
the right architectural seam instead of being patched 1:1), and a
12-step sequenced task list (T-CUT-01 … T-CUT-12) that supersedes the
struck-through tasks above. That file is now the authoritative task list
for this remaining work; this file's Phase 3/5/6 entries are kept only for
history.
