# Tasks: Ollama Model Integration

**Input**: Design documents from `specs/006-ollama-model-integration/`

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Test strategy**: Integration tests (`@pytest.mark.integration`) use live Ollama at
`http://localhost:11434` — no mocking. Unit tests have no marker and run with no live
services. See plan.md §Test Strategy.

**BDD coverage**: 6 `.feature` files in `specs/006-ollama-model-integration/features/`;
step-defs implemented as pytest functions in `tests/test_ollama.py`.

---

## Phase 1: Setup (Test infrastructure additions)

**Purpose**: Extend the existing test harness and Justfile with Ollama-specific fixtures
and recipes. The conftest cleanup here is a blocker: the existing aiohttp mock prevents
real `aiohttp.ClientSession` from working in integration tests.

- [x] T001 Add `system: System tests requiring full docker-compose harness` to `[tool.pytest.ini_options] markers` in `pyproject.toml` (note: `integration` and `unit` markers already exist)
- [x] T002 Fix `tests/conftest.py`: (a) remove the module-level duplicate class definitions (lines 80–159) — keep only the `pytest_configure` hook versions; (b) **remove the `aiohttp` mock entirely** — real `aiohttp` is installed and the mock blocks Ollama integration tests; (c) fix `MockPromptServer.instance = None` class attribute followed immediately by instance override; (d) add `ollama_host`, `ollama_available`, and `skip_if_no_ollama` autouse fixtures per plan.md §Test Strategy; confirm all 76 existing tests still pass after
- [x] T003 [P] Add `test`, `test-unit`, `test-integration`, and `test-system` recipes to `Justfile` per plan.md §Test Strategy
- [x] T004 [P] Create empty `tests/test_ollama.py` with module docstring and import skeleton (`import pytest`, `import asyncio`, `import aiohttp`; `from comfydv.ollama import ...` — will fail until ollama.py exists, so use a lazy import or comment out until Phase 3)

---

## Phase 2: Broken Windows

**Purpose**: Fix every code quality issue found in the existing codebase before adding new
code. BEACON principle: "Any TODOs, warnings, or failing tests I'm walking past?" — walk
past nothing.

- [x] T005 Fix `pyproject.toml`: add `requires-python = ">=3.11"` (eliminates constant `uv` warnings); replace `description = "Add your description here"` with the real package description; **remove the `[project.scripts]` `comfydv = "comfydv:main"` entry** — no `main()` function exists anywhere in the package (running `comfydv` as CLI would immediately error)
- [x] T006 Fix root `__init__.py`: remove the `if "pytest" not in sys.modules:` guard (code smell — conftest.py already installs all ComfyUI mocks before any import, making the guard unnecessary and surprising); make the import unconditional; fix the E501 on the 218-character `@description` docstring by wrapping it at 88 chars; verify `uv run pytest` still passes
- [x] T007 Clean up `src/comfydv/circuit_breaker.py`: remove the 20-line copy-pasted ComfyUI API boilerplate docstring from `INPUT_TYPES` — it describes the ComfyUI framework's type system, not the CircuitBreaker's specific inputs, and is identical boilerplate already present in `random_choice.py`; leave a single-line docstring or none (the method body is self-documenting)
- [x] T008 Clean up `src/comfydv/random_choice.py`: (a) remove the 20-line copy-pasted `INPUT_TYPES` boilerplate docstring (same as T007); (b) remove the dead triple-quoted string literal at class body level (lines ~46–53) — it is not a docstring attached to any method, never executed, and describes ComfyUI's internal caching mechanism rather than RandomChoice's behaviour
- [x] T009 Clean up `src/comfydv/format_string.py`: (a) investigate the `# noqa: F401` on `from server import PromptServer` — run `uv run ruff check --select F401 src/comfydv/format_string.py` without the suppression to determine if ruff still flags it; remove the noqa if the flag is gone; (b) remove the two `# type: ignore` comments on lines 533–534 (`config["inputs"][key] = ...` and `config["outputs"].append(...)`) by narrowing the `config` dict type annotation so the assignments are type-safe without suppression
- [x] T010 Fix `scripts/take_screenshots.py`: remove the unused `h_pad: float = 80` and `v_pad: float = 60` parameters from `_frame_node()` — they are accepted but never read (ruff ARG001); if horizontal/vertical padding is needed in future the parameters can be re-added at that point

---

## Phase 3: Foundational (Blocking prerequisites)

**Purpose**: Shared infrastructure that all 14 nodes depend on. No user story task may
begin until this phase is complete.

**⚠️ CRITICAL**: These tasks produce `ollama.py` skeleton and `ollama.js` skeleton.
All US phases import from these files.

- [x] T011 Create `src/comfydv/ollama.py` with: `OllamaClientType` (str subclass), `_run_async()`, async `_fetch_models(host)`, async `_post_json(url, payload)`, module-level `_DEFAULT_MODELS` list (populated at import time by `_run_async(_fetch_models("http://localhost:11434"))` with graceful fallback), and the `if "comfy" in sys.modules:` runtime guard for `PromptServer` import; `logger = logging.getLogger(__name__)`
- [x] T012 Add `GET /dv/ollama/models` PromptServer route in `src/comfydv/ollama.py`: accepts `host` query param, calls `_fetch_models(host)`, returns `{"models": [...]}` or `{"error": "..."}` with HTTP 503 on failure
- [x] T013 Create `src/js/ollama.js` with the `app.registerExtension` skeleton targeting `OllamaModelSelector`, `OllamaLoadModel`, and `OllamaChatCompletion`; stub `beforeRegisterNodeDef` that calls `GET /dv/ollama/models?host=...` and a placeholder `refreshModelDropdown()` function
- [x] T014 Update `src/comfydv/__init__.py`: add import of all 14 node classes from `.ollama` and register them in `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` (nodes can be stubs that raise `NotImplementedError` at this stage); update `tests/test_ollama.py` import skeleton now that `ollama.py` exists

**Checkpoint**: `uv run python -c "import comfydv"` must succeed; `uv run pytest tests/test_packaging.py` may have new failures (stubs not yet implemented — that's expected).

---

## Phase 4: US1 — Configure Ollama Connection (Priority: P1) 🎯 MVP start

**Goal**: OllamaClient node creates a typed connection handle from a host URL.

**Independent Test**: `uv run pytest -m integration -k "test_client"` — calls no model inference.

**Feature file**: `specs/006-ollama-model-integration/features/us1_ollama_connection.feature`

### User Story 1 — TDD pairs

- [x] T015-T [US1] Write FAILING integration test `test_client_outputs_host` in `tests/test_ollama.py`: step defs for "Default host connects to local Ollama" — assert `OllamaClient().create_client(host="http://localhost:11434")` returns `("http://localhost:11434",)` (red)
- [x] T015-I [US1] Implement `OllamaClient` class in `src/comfydv/ollama.py`: `INPUT_TYPES` with `host` STRING widget defaulting to `"http://localhost:11434"`; `FUNCTION="create_client"`; `RETURN_TYPES=("OLLAMA_CLIENT",)`; `create_client(host)` returns `(OllamaClientType(host),)` so T015-T passes (green)
- [x] T016-T [US1] Write FAILING integration test `test_unreachable_host_raises` in `tests/test_ollama.py`: step defs for "Unreachable host surfaces a named error" — call `OllamaChatCompletion().chat(client="http://localhost:19999", ...)` and assert exception message names the host (red)
- [x] T016-I [US1] Add unreachable-host error handling to `_post_json()` in `src/comfydv/ollama.py`: catch `aiohttp.ClientConnectionError` and re-raise as `RuntimeError("Cannot reach Ollama at {url}: {reason}")` so T016-T passes (green)

**Checkpoint**: `uv run pytest -m integration -k "test_client or test_unreachable"` green.

---

## Phase 5: US2 — Browse and Select Available Models (Priority: P1)

**Goal**: OllamaModelSelector lists models from live Ollama; JS endpoint populates dropdowns.

**Independent Test**: `uv run pytest -m integration -k "test_model_selector or test_fetch_models"` — no inference, only list call.

**Feature file**: `specs/006-ollama-model-integration/features/us2_model_selection.feature`

### User Story 2 — TDD pairs

- [x] T017-T [US2] Write FAILING integration test `test_fetch_models_returns_list` in `tests/test_ollama.py`: step defs for "Dropdown lists all installed models" — call `_run_async(_fetch_models("http://localhost:11434"))` and assert returns a non-empty list of strings (red)
- [x] T017-I [US2] Complete `_fetch_models(host)` in `src/comfydv/ollama.py`: `GET {host}/api/tags`, parse `data["models"]`, return `[m["name"] for m in models]`; graceful fallback to `["(start Ollama to see models)"]` on `ClientConnectionError` so T017-T passes (green)
- [x] T018-T [US2] Write FAILING integration test `test_model_selector_outputs_name` in `tests/test_ollama.py`: step defs for "Selected model name is the node output" — call `OllamaModelSelector().select_model(client="http://localhost:11434", model="embeddinggemma:latest")` and assert output tuple is `("embeddinggemma:latest",)` (red)
- [x] T018-I [US2] Implement `OllamaModelSelector` in `src/comfydv/ollama.py`: `INPUT_TYPES` with `client: OLLAMA_CLIENT` and `model: COMBO` (populated from `_DEFAULT_MODELS`); `FUNCTION="select_model"`; `select_model(client, model)` returns `(model,)` so T018-T passes (green)
- [x] T019-T [US2] Write FAILING integration test `test_ollama_models_endpoint` in `tests/test_ollama.py`: step defs for "GET /dv/ollama/models returns model list" — call the handler function directly with a mock request carrying `?host=http://localhost:11434` and assert JSON contains `"models"` key with a list (red)
- [x] T019-I [US2] Complete `src/js/ollama.js`: implement `refreshModelDropdown(node, host)` that calls `GET /dv/ollama/models?host=...`; hook `onNodeCreated` for `OllamaModelSelector` to auto-refresh; add "⟳" refresh button so T019-T passes (green)

**Checkpoint**: `uv run pytest -m integration -k "test_fetch or test_model_selector or test_client"` all green.

---

## Phase 6: US3 — Load and Unload Models (Priority: P2)

**Goal**: OllamaLoadModel and OllamaUnloadModel control model residency; **Issue #1 fixed** for OllamaLoadModel.

**Independent Test**: `uv run pytest -m integration -k "test_load or test_unload"` — requires Ollama but no inference.

**Feature file**: `specs/006-ollama-model-integration/features/us3_model_lifecycle.feature`

### User Story 3 — TDD pairs

- [x] T020-T [US3] Write FAILING unit test `test_empty_model_raises_before_http` in `tests/test_ollama.py`: step defs for "Empty model name is rejected before contacting Ollama" — call `OllamaLoadModel().load_model(client="http://localhost:11434", model="")` and assert raises `ValueError` without network I/O (red)
- [x] T020-I [US3] Implement `OllamaLoadModel` stub in `src/comfydv/ollama.py` with empty-model guard: `if not model.strip(): raise ValueError("model name cannot be empty")` so T020-T passes (green)
- [x] T021-T [US3] Write FAILING integration test `test_load_model_returns_name` in `tests/test_ollama.py`: step defs for "Load Model loads model into Ollama memory" — call `OllamaLoadModel().load_model(client=ollama_host, model="embeddinggemma:latest")` and assert output is `("embeddinggemma:latest",)` (red)
- [x] T021-I [US3] Complete `OllamaLoadModel.load_model()` in `src/comfydv/ollama.py`: `POST {client}/api/show {"model": model, "keep_alive": "-1"}`; return `(model,)`; `INPUT_TYPES` uses COMBO from `_DEFAULT_MODELS` so T021-T passes (green)
- [x] T022-T [US3] Write FAILING integration test `test_unload_model_returns_name` in `tests/test_ollama.py`: step defs for "Unload Model evicts model from Ollama memory" — call `OllamaUnloadModel().unload_model(client=ollama_host, model="embeddinggemma:latest")` and assert output is `("embeddinggemma:latest",)` (red)
- [x] T022-I [US3] Implement `OllamaUnloadModel` in `src/comfydv/ollama.py`: `POST {client}/api/show {"model": model, "keep_alive": 0}`; return `(model,)` so T022-T passes (green)
- [x] T023-T [US3] Write FAILING integration test `test_load_model_dropdown_not_text_box` in `tests/test_ollama.py`: step defs for "Load Model shows live dropdown (fixes Issue #1)" — assert `OllamaLoadModel.INPUT_TYPES()["required"]["model"]` is a list (COMBO) not `("STRING", {})` (red — current stub has wrong type)
- [x] T023-I [US3] Update `OllamaLoadModel.INPUT_TYPES()` in `src/comfydv/ollama.py` to use COMBO; extend `ollama.js` `beforeRegisterNodeDef` to cover `OllamaLoadModel` so T023-T passes (green — Issue #1 fixed for LoadModel)

**Checkpoint**: `uv run pytest -k "test_load or test_unload or test_empty_model"` green.

---

## Phase 7: US4 — Generate Text via Chat Completion (Priority: P2)

**Goal**: OllamaChatCompletion sends prompt+history to Ollama and returns response+updated history. **Issue #1 fully fixed**.

**Independent Test**: `uv run pytest -m integration -k "test_chat"` — requires Ollama with a generative model.

**Feature file**: `specs/006-ollama-model-integration/features/us4_chat_completion.feature`

### User Story 4 — TDD pairs

- [x] T024-T [US4] Write FAILING integration test `test_chat_completion_single_turn` in `tests/test_ollama.py`: step defs for "Single-turn completion returns non-empty response" — call `OllamaChatCompletion().chat(client=ollama_host, model="lukey03/qwen3.5-9b-abliterated-vision:latest", prompt="Say exactly: pong", system="", history=[], options={})` and assert `response` is non-empty STRING and `len(updated_history) == 2` (red)
- [x] T024-I [US4] Implement `OllamaChatCompletion` in `src/comfydv/ollama.py`: `POST {client}/api/chat` with `{"model": model, "messages": history + [{"role":"user","content":prompt}], "stream": false}`; append assistant turn to history; return `(response_text, updated_history)`; COMBO for model (fixes Issue #1) so T024-T passes (green)
- [x] T025-T [US4] Write FAILING integration test `test_chat_completion_multi_turn` in `tests/test_ollama.py`: step defs for "Multi-turn completion receives full conversation context" — two-turn exchange; second asks "What is my name?" after first established "My name is Alice"; assert "Alice" in response (red)
- [x] T025-I [US4] Verify history is correctly prepended to `messages` list in `OllamaChatCompletion.chat()` — confirm T025-T passes; no structural change needed if T024-I was correct (green)
- [x] T026-T [US4] Write FAILING integration test `test_chat_completion_dropdown_not_text_box` in `tests/test_ollama.py`: step defs for "Chat Completion shows live dropdown (fixes Issue #1)" — assert `OllamaChatCompletion.INPUT_TYPES()["required"]["model"]` is a list (COMBO) not `("STRING", {})` (red)
- [x] T026-I [US4] Update `OllamaChatCompletion.INPUT_TYPES()` in `src/comfydv/ollama.py` to use COMBO; extend `ollama.js` to cover `OllamaChatCompletion` so T026-T passes (green — Issue #1 fully fixed for all affected nodes)

**Checkpoint**: `uv run pytest -m integration -k "test_chat"` green; Issue #1 closed across all three affected nodes.

---

## Phase 8: US5 — Tune Inference with Composable Option Nodes (Priority: P3)

**Goal**: 7 option nodes that chain via `OLLAMA_OPTIONS` and forward parameters to ChatCompletion.

**Independent Test**: Unit tests (no marker) for dict merging; integration test for deterministic output.

**Feature file**: `specs/006-ollama-model-integration/features/us5_composable_options.feature`

### User Story 5 — TDD pairs

- [x] T027-T [US5] Write FAILING unit tests `test_option_temperature_merge`, `test_option_seed_merge`, `test_option_extends_existing` in `tests/test_ollama.py`: step defs for option dict merging — assert `OllamaOptionTemperature().set_temperature(options={}, temperature=0.5)` returns `({"temperature": 0.5},)` and chaining extends the dict (red)
- [x] T027-I [US5] Implement `OllamaOptionTemperature` and `OllamaOptionSeed` in `src/comfydv/ollama.py`: each accepts optional `OLLAMA_OPTIONS` input and a value; merges `{key: value}` into the options dict copy; returns `(extended_options,)` so T027-T passes (green)
- [x] T028-T [US5] Write FAILING unit tests `test_option_max_tokens`, `test_option_top_p`, `test_option_top_k`, `test_option_repeat_penalty`, `test_option_extra_body_valid_json`, `test_option_extra_body_invalid_json_raises` in `tests/test_ollama.py` (red)
- [x] T028-I [US5] Implement `OllamaOptionMaxTokens`, `OllamaOptionTopP`, `OllamaOptionTopK`, `OllamaOptionRepeatPenalty`, `OllamaOptionExtraBody` in `src/comfydv/ollama.py`; ExtraBody parses STRING as JSON; raises `ValueError` on invalid JSON so T028-T passes (green)
- [x] T029-T [US5] Write FAILING integration test `test_temperature_zero_is_deterministic` in `tests/test_ollama.py`: step defs for "Temperature 0.0 produces deterministic output" — run ChatCompletion twice same prompt, `temperature=0.0`, `seed=42`; assert both responses equal (red)
- [x] T029-I [US5] Wire `options` dict into `OllamaChatCompletion.chat()` in `src/comfydv/ollama.py`: include `"options": options` in the `/api/chat` POST body when options is non-empty so T029-T passes (green)

**Checkpoint**: `uv run pytest -k "option or test_temperature_zero"` green.

---

## Phase 9: US6 — Inspect Conversation History (Priority: P3)

**Goal**: OllamaDebugHistory and OllamaHistoryLength inspect history lists.

**Independent Test**: Pure unit tests — no live services.

**Feature file**: `specs/006-ollama-model-integration/features/us6_history_inspection.feature`

### User Story 6 — TDD pairs

- [x] T030-T [US6] Write FAILING unit tests `test_debug_history_two_turns`, `test_debug_history_empty` in `tests/test_ollama.py`: step defs for "Debug History shows both turns as a string" — assert `OllamaDebugHistory().debug(history=[...])` returns a tuple whose single STRING contains both turns (red)
- [x] T030-I [US6] Implement `OllamaDebugHistory` in `src/comfydv/ollama.py`: `FUNCTION="debug"`; `debug(history)` returns `(json.dumps(history, indent=2),)` so T030-T passes (green)
- [x] T031-T [US6] Write FAILING unit tests `test_history_length_three`, `test_history_length_empty` in `tests/test_ollama.py`: step defs for "History Length counts turns correctly" — assert `OllamaHistoryLength().length(history=[...])` returns `(3,)` and `(0,)` for empty (red)
- [x] T031-I [US6] Implement `OllamaHistoryLength` in `src/comfydv/ollama.py`: `FUNCTION="length"`; `RETURN_TYPES=("INT",)`; `length(history)` returns `(len(history),)` so T031-T passes (green)

**Checkpoint**: `uv run pytest -k "debug_history or history_length"` green; all 14 nodes implemented.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Packaging integrity, logging harmonisation across ALL nodes, docs, and quality gate.

- [x] T032 Update `tests/test_packaging.py` to assert all 14 new node class names appear in `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`
- [x] T033 [P] Update `README.md` and `docs/index.md` to add an "Ollama" section to the node reference table covering all 14 nodes
- [x] T034 [P] Update `comfy-manager-entry.json` `"nodename"` array to include the display names of all 14 new nodes

### Logging harmonisation — TDD pair

**Scope**: Every module in `src/comfydv/` must follow the same logging contract: `DEBUG`
for trace/verbose, `WARNING` for degraded-mode (ComfyUI absent), `ERROR` for caught
failures. No `print()` in library code. Dead literals and useless re-raises removed.

**Remaining issues not yet covered by Phase 2 Broken Windows tasks:**
- `format_string.py:34` — `print(…)` → `logger.warning()`
- `circuit_breaker.py:13` — `logger.debug(…)` → `logger.warning()` for ComfyUI-absent branch
- `random_choice.py:71–72` — `except Exception as e: raise e` → `logger.error(…); raise`
- `ollama.py` ComfyUI-absent branches must use `logger.warning()`

- [x] T035-T Extend `tests/test_logging.py` with `TestLoggingConsistency`: (a) AST-walk all `.py` files under `src/comfydv/` and assert zero `print()` calls; (b) assert `circuit_breaker.py` ComfyUI-absent path emits `WARNING` not `DEBUG`; (c) assert `random_choice.py` exception path emits an `ERROR` record; (d) assert `ollama.py` ComfyUI-absent path emits `WARNING`; confirm all four assertions are red against the current codebase before committing (red)
- [x] T035-I Fix `src/comfydv/format_string.py` (`print()` → `logger.warning()`), `src/comfydv/circuit_breaker.py` (`logger.debug()` → `logger.warning()` on absent-ComfyUI branch), `src/comfydv/random_choice.py` (replace bare re-raise with `logger.error("RandomChoice: unexpected error: %s", e); raise`), `src/comfydv/ollama.py` (all absent-ComfyUI branches → `logger.warning()`); verify `uv run pytest tests/test_logging.py` is fully green (green)

- [x] T036 Run full quality gate in order: `uv run ruff check --fix && uv run ruff format`, then `uv run ty check`, then `uv run pytest` (all marks), then `beacon doctor --strict`; fix any failures before proceeding
- [x] T037 Run `just ci-smoke` to confirm CI smoke test passes with all 14 nodes registered

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Broken Windows)**: Depends on Phase 1 — the conftest fix in T002 must land before these structural changes to ensure tests still pass; Phases 2 tasks are independent of each other and can run in parallel
- **Phase 3 (Foundational)**: Depends on Phase 1 and Phase 2 — BLOCKS all user stories
- **Phase 4 (US1)**: Depends on Phase 3 — OllamaClient is prerequisite for all downstream nodes
- **Phase 5 (US2)**: Depends on Phase 4 — model selector depends on `_fetch_models`
- **Phase 6 (US3)**: Depends on Phase 5 — load/unload depends on model fetching infrastructure
- **Phase 7 (US4)**: Depends on Phase 6 — Issue #1 fix completes here
- **Phase 8 (US5)**: Depends on Phase 7 — option nodes wired into ChatCompletion
- **Phase 9 (US6)**: Depends on Phase 7 — history output from ChatCompletion is the test fixture
- **Phase 10 (Polish)**: Depends on all prior phases; T035-T/I before T036 (quality gate)

### Within each user story: Red → Green → Refactor

Every `-T` commit is pushed alone (failing test). The `-I` commit follows on its own
(passing). No test + implementation in the same commit.

### Parallel opportunities

- T003, T004 can run in parallel with T001, T002 (within Phase 1)
- T005–T010 (Phase 2 broken windows) are all independent — run in parallel
- T027-T through T028-I (US5 unit tests) can run in parallel with T029-T (integration)
- T030-T/I and T031-T/I (Phase 9) can run in parallel with each other
- T033, T034 (Phase 10) can run in parallel

---

## BDD coverage summary

| Feature file | Scenarios | Covered by |
|---|---|---|
| `us1_ollama_connection.feature` | 3 | T015-T, T016-T |
| `us2_model_selection.feature` | 3 | T017-T, T018-T, T019-T |
| `us3_model_lifecycle.feature` | 4 | T020-T, T021-T, T022-T, T023-T |
| `us4_chat_completion.feature` | 4 | T024-T, T025-T, T026-T |
| `us5_composable_options.feature` | 3 | T027-T, T029-T |
| `us6_history_inspection.feature` | 3 | T030-T, T031-T |
| *(logging consistency — tested in `tests/test_logging.py`)* | 4 checks | T035-T |

---

## Implementation Strategy

### MVP scope (Phases 1–4: US1 only)

Complete Phases 1–4. After T016-I, you have a working `OllamaClient` node and a clean
baseline (broken windows fixed). This is the foundation that proves infrastructure
end-to-end.

### Incremental delivery

After each phase checkpoint, run `just ci-smoke` to confirm the harness still starts
cleanly.

---

## Notes

- `[P]` = different files, no inter-task dependencies at that point
- `-T` commit: only the failing test — confirm RED before committing
- `-I` commit: only the implementation — confirm GREEN before committing
- Phase 2 (Broken Windows) tasks are small and should take < 30 min total; do them first
- The `_DEFAULT_MODELS` module-level list (populated at `ollama.py` import time) is the static COMBO source; the JS widget overrides it at runtime
- `beacon doctor --strict` and `spec-bdd-coverage` checks must pass before opening the PR
