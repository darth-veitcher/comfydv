# Feature Specification: Standardise Node Logging

**Feature Branch**: `001-standardise-logging`

**Created**: 2026-06-28

**Status**: Draft

**Input**: Replace ad-hoc print/logging with standard Python library logging across all nodes — remove hardcoded DEBUG level, convert coloured print() calls in RandomChoice and CircuitBreaker to logger calls, strip the diagnostic print dump from FormatString, add NullHandler to package root, and drop colorama/termcolor/rich from runtime dependencies

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Silent Normal Operation (Priority: P1)

A ComfyUI user who has installed comfydv nodes runs a workflow. They expect the ComfyUI console to be quiet — no diagnostic noise from the custom nodes during normal execution.

**Why this priority**: This directly fixes the reported issue (#4). Every keystroke in the template field currently emits 8 lines to the console, making the plugin actively annoying to use.

**Independent Test**: Install the nodes, open a workflow with a FormatString node, type into the template field, queue a prompt. The ComfyUI console should show zero output from comfydv modules.

**Acceptance Scenarios**:

1. **Given** a ComfyUI session with comfydv loaded, **When** a user types into the FormatString template field, **Then** no lines are written to the ComfyUI console from this package.
2. **Given** a running queue prompt that includes a FormatString, RandomChoice, or CircuitBreaker node, **When** the node executes successfully, **Then** no output appears in the ComfyUI console from this package.
3. **Given** a ComfyUI session, **When** the server starts and loads the comfydv custom nodes, **Then** no startup output (beyond ComfyUI's own "Loaded custom node" line) is emitted from this package.

---

### User Story 2 — Errors Still Surface (Priority: P1)

A workflow creator has a broken Jinja2 template (syntax error). They expect to see a clear error in the ComfyUI console telling them what went wrong, without having to enable debug logging.

**Why this priority**: Silent failure on errors would be worse than the current verbosity. Error visibility must be preserved.

**Independent Test**: Create a FormatString node with an invalid Jinja2 template (e.g. `{{ unclosed`). Queue the prompt. An error message must appear in the ComfyUI console.

**Acceptance Scenarios**:

1. **Given** a FormatString node with an invalid Jinja2 template, **When** the prompt is queued, **Then** an error message describing the template fault appears in the ComfyUI console.
2. **Given** a FormatString node with a `save_path` that cannot be written, **When** the prompt executes, **Then** an error message about the failed save appears in the console.
3. **Given** a CircuitBreaker node with `status=False`, **When** the prompt executes, **Then** the queue run halts and a message is visible in the console at INFO level or above.

---

### User Story 3 — Developer Debug Mode (Priority: P2)

A developer debugging a custom workflow wants to see verbose output from comfydv nodes. They configure Python's logging system to enable DEBUG for the `comfydv` logger and get detailed traces without any code changes to the package.

**Why this priority**: Debug visibility must still be available — just opt-in rather than on by default.

**Independent Test**: In a Python environment with comfydv imported, configure `logging.getLogger("comfydv").setLevel(logging.DEBUG)` with a stream handler. Invoke `FormatString.format_string(...)`. Detailed trace lines should appear.

**Acceptance Scenarios**:

1. **Given** a Python environment where `logging.getLogger("comfydv").setLevel(logging.DEBUG)` is set, **When** any node function executes, **Then** detailed trace messages (template content, extracted keys, output tuple) appear in the log output.
2. **Given** a Python environment with no logging configuration for `comfydv`, **When** any node function executes, **Then** no output appears (NullHandler absorbs everything).

---

### Edge Cases

- What happens when ComfyUI's root logger has no handlers configured? The NullHandler on the package logger prevents a "No handlers could be found" warning.
- What happens when a third-party tool sets the `comfydv` logger level before import? The package must not override it — `setLevel` must not be called on import.
- What happens if `colorama`/`termcolor`/`rich` are removed but something else in the ComfyUI environment already provides them? No impact — the nodes simply no longer import them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The package root logger (`comfydv`) MUST have a `NullHandler` added in `__init__.py` so that a host with no logging configuration does not see "No handlers" warnings.
- **FR-002**: No module in the package MUST call `logger.setLevel(...)` at import time or module level.
- **FR-003**: No module in the package MUST add handlers to any logger.
- **FR-004**: All calls to `print()` used for diagnostic/trace output MUST be replaced with the appropriate `logging` level call (`debug`, `info`, `warning`, `error`).
- **FR-005**: Log calls in code paths that execute on every keystroke (`IS_CHANGED`, `update_widget`, the aiohttp route handler for template updates) MUST be at `DEBUG` level only.
- **FR-006**: Template render errors (Jinja2 `TemplateSyntaxError`, Python `KeyError`) MUST remain at `ERROR` level.
- **FR-007**: File-save failures MUST remain at `ERROR` level.
- **FR-008**: The `colorama`, `termcolor`, and `rich` packages MUST be removed from the `[project.dependencies]` list in `pyproject.toml` (they are no longer imported by any node).
- **FR-009**: The `from rich import print` override in `format_string.py` MUST be removed; the built-in `print` must not be shadowed.
- **FR-010**: All existing tests MUST continue to pass after the changes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero lines written to stdout/stderr by comfydv modules during a normal node execution (verified by capturing output in the test suite).
- **SC-002**: At least one ERROR-level log record is produced when a FormatString node receives an invalid template (verified by test asserting `caplog` or log record count > 0 at ERROR).
- **SC-003**: Setting `logging.getLogger("comfydv").setLevel(logging.DEBUG)` causes DEBUG records to appear; removing that configuration causes zero records — verified by test.
- **SC-004**: `pip show comfydv` (or `uv pip show comfydv`) lists no dependency on `colorama`, `termcolor`, or `rich`.
- **SC-005**: `uv run pytest` exits 0 with no new failures.

## Assumptions

- ComfyUI's own logging configuration is not changed — this package only controls its own logger hierarchy under `comfydv.*`.
- The `rich`, `colorama`, and `termcolor` packages are not used anywhere else in the package beyond the logging/print calls being removed (confirmed by grep of the source).
- The `aiohttp` dependency remains (it is used for the web routes, not just logging).
- No user-facing ComfyUI UI changes are required; this is entirely a server-side/console change.
