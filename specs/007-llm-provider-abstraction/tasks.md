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

- [ ] T001 Add `pydantic-ai` and `openai` to `pyproject.toml` dependencies; curate the addition into `requirements.txt` per [ADR-003](../../project-management/ADRs/ADR-003-requirements-txt-authoring-policy.md)
- [ ] T002 [P] Create `src/comfydv/_llm/__init__.py` (empty package init)

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 [P] Define `Message`, `ModelStatus`, `ModelInfo` in `src/comfydv/_llm/provider.py` per `data-model.md`
- [ ] T004 Define the `LLMProvider` `Protocol` in `src/comfydv/_llm/provider.py` per `contracts/llm_provider_protocol.md` (depends on T003)
- [ ] T005 [P] Add the `LLM_CLIENT` custom ComfyUI socket type constant in `src/comfydv/ollama.py`, alongside the existing `OLLAMA_CLIENT` declaration
- [ ] T006 Scaffold `OllamaProvider.__init__(self, host, headers)` in `src/comfydv/_llm/ollama_provider.py`, porting the existing module-level `_post_json`/`_fetch_models` helpers from `ollama.py` into it as private methods — behavior-preserving port, not a rewrite (depends on T004)

**Checkpoint**: protocol + provider skeleton exist; user story work can begin.

---

## Phase 3: User Story 1 — Connect to a local server and get chat responses (Priority: P1) 🎯 MVP

**Goal**: A workflow author wires a client node into a generic chat node and gets a text response.

**Independent Test**: Wire `OllamaClient` → `ChatCompletion`, run against a live server, confirm text output.

- [ ] T007-T [US1] Write FAILING test: `OllamaClient` node constructs and outputs an `OllamaProvider` via the `LLM_CLIENT` socket, in `tests/test_ollama.py` (witnesses `features/us1_connect_and_chat.feature` scenario "Client node feeds a chat node")
- [ ] T007-I [US1] Update `OllamaClient` in `src/comfydv/ollama.py` to construct and output an `OllamaProvider` via `LLM_CLIENT` — makes T007-T pass
- [ ] T008-T [P] [US1] Write FAILING test: `OllamaProvider.chat()` returns model text via the existing `/api/chat` aiohttp call, in `tests/test_llm_provider.py`
- [ ] T008-I [US1] Implement `OllamaProvider.chat()` in `src/comfydv/_llm/ollama_provider.py` (port of the existing non-structured path from `OllamaChatCompletion.chat`) — makes T008-T pass
- [ ] T009-T [US1] Write FAILING test: generic `ChatCompletion` node (non-structured) calls `provider.chat()` and surfaces a clear error on an unreachable host, in `tests/test_ollama.py` (witnesses `features/us1_connect_and_chat.feature` scenarios "Client node feeds a chat node" and "Unreachable server surfaces a clear error")
- [ ] T009-I [US1] Rename `OllamaChatCompletion` → `ChatCompletion` in `src/comfydv/ollama.py`, delegate the non-structured path to `LLMProvider.chat()`, update `NODE_CLASS_MAPPINGS`/`NODE_DISPLAY_NAME_MAPPINGS` in `src/comfydv/__init__.py` — makes T009-T pass (depends on T007-I, T008-I)
- [ ] T010-T [US1] Write FAILING test: two `ChatCompletion` nodes sharing one `OllamaClient` both pick up a host change, in `tests/test_ollama.py` (witnesses `features/us1_connect_and_chat.feature` scenario "One client node configures multiple chat nodes")
- [ ] T010-I [US1] Verify/adjust that `OllamaClient` → `OllamaProvider` construction happens per node execution (not stale-cached), so a shared client's host change propagates — makes T010-T pass

**Checkpoint**: US1 fully functional and independently testable (MVP).

---

## Phase 4: User Story 2 — Structured, validated output (Priority: P1)

**Goal**: The chat node's `structured_output` toggle returns validated typed fields via the shared `pydantic-ai` mechanism.

**Independent Test**: Enable `structured_output` with a schema, run against a model, confirm typed sockets are populated and never blank.

- [ ] T011-T [P] [US2] Write FAILING test: `chat_structured()` builds a dynamic `pydantic` model via `create_model()` from a JSON-Schema input and returns validated fields, in `tests/test_llm_provider.py` (witnesses `features/us2_structured_output.feature` scenario "Valid structured response exposes typed fields")
- [ ] T011-I [US2] Implement the shared `chat_structured()` helper in `src/comfydv/_llm/chat.py` using `pydantic-ai`'s `Agent`/`output_type` through `OpenAIProvider(base_url=<host>/v1)`, reusing the existing JSON-Schema→pydantic `create_model()` logic ported from `ollama.py` — makes T011-T pass (depends on T004)
- [ ] T012-T [US2] Write FAILING test: invalid, incomplete, or blank-required-field responses trigger automatic retry up to `max_retries`, in `tests/test_llm_provider.py` (witnesses `features/us2_structured_output.feature` scenario "Invalid response triggers automatic retry")
- [ ] T012-I [US2] Implement the bounded retry loop (0–5, matching ADR-006's existing contract) around the `pydantic-ai` call in `src/comfydv/_llm/chat.py` — makes T012-T pass (depends on T011-I)
- [ ] T013-T [US2] Write FAILING test: exhausted retries raise `RuntimeError` naming the model, attempt count, and a truncated last-response snippet, in `tests/test_llm_provider.py` (witnesses `features/us2_structured_output.feature` scenario "Exhausted retries fail clearly instead of passing through bad data")
- [ ] T013-I [US2] Implement the exhausted-retry error path in `src/comfydv/_llm/chat.py`, matching ADR-006's existing error message contract exactly — makes T013-T pass (depends on T012-I)
- [ ] T014-T [US2] Write FAILING test: `ChatCompletion`'s `structured_output=True` path wires a schema through `chat_structured()` to per-field dynamic ComfyUI output sockets, in `tests/test_ollama.py`
- [ ] T014-I [US2] Wire `ChatCompletion`'s existing `structured_output`/`output_schema` inputs to `LLMProvider.chat_structured()`, preserving the existing dynamic-socket (`RETURN_TYPES` mutation via `unique_id`) UX from ADR-006 — makes T014-T pass (depends on T009-I, T013-I)

**Checkpoint**: US1 + US2 both independently functional — matches today's Ollama capability, now on the shared mechanism.

---

## Phase 5: User Story 3 — Manage model residency (Priority: P2)

**Goal**: List/load/unload models through generic nodes against any connected provider.

**Independent Test**: List models via `LLMModelSelector`; load/unload one via `LLMLoadModel`/`LLMUnloadModel`; confirm status changes.

- [ ] T015-T [P] [US3] Write FAILING test: `OllamaProvider.list_models()` returns `ModelInfo` entries with status normalized into `ModelStatus` (never emitting `sleeping`/`downloading`), in `tests/test_llm_provider.py` (witnesses `features/us3_model_lifecycle.feature` scenario "List models with current status")
- [ ] T015-I [US3] Implement `OllamaProvider.list_models()` in `src/comfydv/_llm/ollama_provider.py` (port of the existing `_fetch_models`/`/api/tags` logic, reusing the existing `_TTLLRUCache`) — makes T015-T pass (depends on T006)
- [ ] T016-T [P] [US3] Write FAILING test: `OllamaProvider.load_model()`/`unload_model()` are idempotent and use `keep_alive` semantics equivalent to today's `OllamaLoadModel`/`OllamaUnloadModel`, in `tests/test_llm_provider.py` (witnesses `features/us3_model_lifecycle.feature` scenarios "Load a model into memory" and "Unload a model from memory")
- [ ] T016-I [US3] Implement `OllamaProvider.load_model()`/`unload_model()` in `src/comfydv/_llm/ollama_provider.py` (port of the existing `keep_alive` logic) — makes T016-T pass (depends on T006)
- [ ] T017-T [US3] Write FAILING test: generic `LLMModelSelector` node returns model+status pairs from any connected `LLM_CLIENT`, in `tests/test_ollama.py`
- [ ] T017-I [US3] Rename `OllamaModelSelector` → `LLMModelSelector` in `src/comfydv/ollama.py`, delegate to `LLMProvider.list_models()`, update `NODE_CLASS_MAPPINGS` — makes T017-T pass (depends on T015-I)
- [ ] T018-T [US3] Write FAILING test: generic `LLMLoadModel`/`LLMUnloadModel` nodes call `LLMProvider.load_model()`/`unload_model()` and reflect updated status, in `tests/test_ollama.py`
- [ ] T018-I [US3] Rename `OllamaLoadModel`/`OllamaUnloadModel` → `LLMLoadModel`/`LLMUnloadModel` in `src/comfydv/ollama.py`, delegate to the protocol, update `NODE_CLASS_MAPPINGS` — makes T018-T pass (depends on T016-I)

**Checkpoint**: US1 + US2 + US3 independently functional.

---

## Phase 6: User Story 4 — Reconnect an existing workflow after upgrading (Priority: P3)

**Goal**: A clear old→new node mapping exists, and migrated workflows are output-equivalent.

**Independent Test**: Follow the mapping to reconnect a pre-upgrade workflow; confirm equivalent output.

- [ ] T019-T [US4] Write FAILING test: every renamed/removed node and socket name (`OllamaChatCompletion`, `OllamaModelSelector`, `OllamaLoadModel`, `OllamaUnloadModel`, `OLLAMA_CLIENT`) resolves to a documented replacement via a migration-mapping constant, in `tests/test_ollama.py` (witnesses `features/us4_migration.feature` scenario "Renamed nodes are reported with a documented replacement")
- [ ] T019-I [US4] Add a migration mapping (old node/socket name → new node/socket name) as a module-level constant in `src/comfydv/ollama.py`, and surface it in the replacement nodes' `DESCRIPTION`/docstrings per FR-009 — makes T019-T pass (depends on T009-I, T017-I, T018-I)
- [ ] T020 [US4] Run the full `tests/test_ollama.py` suite against the migrated implementation and confirm every existing assertion still passes unmodified in behavior (SC-003 equivalence check; witnesses `features/us4_migration.feature` scenario "Reconnected workflow produces equivalent output") — regression pass, not a new test
- [ ] T021 [P] [US4] Update `quickstart.md`'s "Migrating an existing pre-upgrade workflow" section if the actual replacement mapping (T019-I) differs from what was drafted at plan time

**Checkpoint**: all four user stories independently functional; migration path documented.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T022 [P] Run `uv run ruff check --fix && uv run ruff format` across `src/comfydv/_llm/` and the modified `ollama.py`/`__init__.py`
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
