# Tasks: Standardise Node Logging

**Input**: Design documents from `specs/001-standardise-logging/`

**Branch**: `001-standardise-logging`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[US#]**: User story label from spec.md
- **-T / -I suffix**: TDD pair — `-T` (write failing test) always committed before its `-I` (implementation)

---

## Phase 1: Setup — Foundational changes (no user story blocked until these land)

**Purpose**: Remove the two package-level violations that cause all nodes to misbehave. These must land first; all user-story work builds on them.

- [x] T001 Add `logging.NullHandler()` to the `comfydv` root logger in `src/comfydv/__init__.py`; remove `from rich import print` import also in `__init__.py` if present
- [x] T002 Remove `logger.setLevel(logging.DEBUG)` from `src/comfydv/format_string.py` (line 29); this is the root cause of issue #4

**Checkpoint**: After T001–T002, importing comfydv no longer forces DEBUG output. User-story work can now begin.

---

## Phase 2: User Story 1 — Silent Normal Operation (Priority: P1) 🎯 MVP

**Goal**: Zero lines written to stdout/stderr by comfydv during any successful node execution.

**Independent Test**: Run `uv run pytest tests/test_logging.py -k us1` — all US1 tests pass and capsys shows no captured output.

### User Story 1 — TDD pairs

- [x] T010-T [US1] Write FAILING tests for silent FormatString execution in `tests/test_logging.py` — step defs for US1 scenarios in `specs/001-standardise-logging/features/us1_silent_normal_operation.feature` (red)
- [x] T010-I [US1] Remove the 8-line diagnostic `print()` block from `FormatString.format_string` in `src/comfydv/format_string.py` (lines 446–469) so T010-T passes (green)
- [x] T011-T [US1] Write FAILING tests asserting `IS_CHANGED` and `update_widget` produce zero stdout in `tests/test_logging.py` (red)
- [x] T011-I [US1] Downgrade all `logger.info(...)` calls inside `IS_CHANGED` and `update_widget` to `logger.debug(...)` in `src/comfydv/format_string.py` so T011-T passes (green)
- [x] T012-T [P] [US1] Write FAILING test for silent `RandomChoice.random_choice` execution in `tests/test_logging.py` (red)
- [x] T012-I [P] [US1] Replace `print(colored(...))` / `pprint(...)` calls in `src/comfydv/random_choice.py` with `logger.debug(...)` calls; add `logger = logging.getLogger(__name__)` and remove `colorama`/`termcolor`/`rich` imports so T012-T passes (green)

**Checkpoint**: `uv run pytest tests/test_logging.py -k us1` green; capsys shows zero comfydv output for any successful execution path.

---

## Phase 3: User Story 2 — Errors Still Surface (Priority: P1)

**Goal**: Template errors, save failures, and CircuitBreaker interrupts emit records at ERROR/INFO — visible in a default ComfyUI session.

**Independent Test**: Run `uv run pytest tests/test_logging.py -k us2` with `caplog` — at least one ERROR record per failure scenario.

### User Story 2 — TDD pairs

- [x] T020-T [US2] Write FAILING tests using `caplog` asserting ERROR records on bad Jinja2 template, missing Simple variable, and failed file save in `tests/test_logging.py` — step defs for `us2_errors_still_surface.feature` (red)
- [x] T020-I [US2] Confirm the three error paths in `FormatString.format_string` already use `logger.error(...)` — add or correct any that don't; convert `print(f"Error loading node state: {e}")` in `load_node_state` to `logger.error(...)` in `src/comfydv/format_string.py` so T020-T passes (green)
- [x] T021-T [P] [US2] Write FAILING test asserting `CircuitBreaker.doit` with `status=False` produces a log record (DEBUG or above) in `tests/test_logging.py` (red)
- [x] T021-I [P] [US2] Add `import logging` and `logger = logging.getLogger(__name__)` to `src/comfydv/circuit_breaker.py`; replace `print("Circuit Breaker triggered")` with `logger.debug("CircuitBreaker: interrupt triggered")` so T021-T passes (green)

**Checkpoint**: `uv run pytest tests/test_logging.py -k us2` green; error scenarios all produce records.

---

## Phase 4: User Story 3 — Developer Debug Mode (Priority: P2)

**Goal**: Setting `logging.getLogger("comfydv").setLevel(logging.DEBUG)` surfaces detailed traces; no config → zero records.

**Independent Test**: Run `uv run pytest tests/test_logging.py -k us3` — DEBUG opt-in and NullHandler default both verified.

### User Story 3 — TDD pairs

- [x] T030-T [US3] Write FAILING tests confirming DEBUG records appear with opt-in config and zero records appear with default NullHandler in `tests/test_logging.py` — step defs for `us3_developer_debug_mode.feature` (red)
- [x] T030-I [US3] Verify that after T001/T010-I/T011-I the NullHandler is the only default handler and DEBUG calls exist in `format_string.py` for the trace paths — add `logger.debug()` calls to `update_widget` for key extraction summary and `format_string` for execution trace so T030-T passes (green)

**Checkpoint**: `uv run pytest tests/test_logging.py -k us3` green; full test suite still passes.

---

## Phase 5: Polish & cross-cutting

**Purpose**: Remove dead runtime dependencies and close the quality gates.

- [x] T040 [P] Remove `colorama`, `termcolor`, and `rich` from `[project.dependencies]` in `pyproject.toml`; run `uv sync` to update `uv.lock`
- [x] T041 [P] Remove `from colorama import just_fix_windows_console`, `just_fix_windows_console()`, `from termcolor import colored`, `from rich.pretty import pprint` dead imports from `src/comfydv/random_choice.py`
- [x] T042 Run `uv run ruff check --fix && uv run ruff format` and fix any remaining lint issues
- [x] T043 Run full test suite `uv run pytest` and confirm exit 0 with no new failures
- [x] T044 Run `beacon doctor --strict` and confirm 0 failures

---

## Dependencies & Execution Order

- **Phase 1 (T001–T002)**: No dependencies — start here
- **Phase 2 (US1)**: Requires Phase 1 complete; T010-T must precede T010-I, T011-T before T011-I, T012-T before T012-I
- **Phase 3 (US2)**: Requires Phase 1; T020-T before T020-I, T021-T before T021-I; can run in parallel with Phase 2 on separate files
- **Phase 4 (US3)**: Requires Phase 1 + Phase 2 (NullHandler must exist); T030-T before T030-I
- **Phase 5 (Polish)**: Requires all prior phases; T040/T041 can run in parallel (different files)

### TDD rule (enforced by `beacon doctor --strict`)
Every `-T` task is committed alone (red) before its `-I` partner. `beacon doctor tdd-commit-discipline` will FAIL if a `-T` and its `-I` appear in the same commit.

---

## Implementation Strategy

### MVP (Phase 1 + Phase 2 only)
1. T001 → T002 (setup)
2. T010-T → T010-I → T011-T → T011-I → T012-T → T012-I (silence the hot path)
3. Validate: `uv run pytest tests/test_logging.py -k us1` green, zero capsys output

This alone fixes issue #4.

### Full delivery
Continue with Phase 3 → 4 → 5 in order. Full suite green before opening the PR.
