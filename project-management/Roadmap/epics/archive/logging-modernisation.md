# Epic: Logging Modernisation

## Status
Done — completed 2026-06-28

## Why now
Issue #4 from a community user reports 8 lines of console output per keystroke in the template field. The root cause is a hardcoded `logger.setLevel(logging.DEBUG)` at module level combined with diagnostic `print()` blocks that were never removed after the FormatString output-order fix. Left unaddressed this makes the nodes unusable in production ComfyUI sessions. This is also a correctness issue: a library must never configure its own log level or add handlers — that violates the Python logging best-practice contract.

## Dependencies
_None._

## Specs
<!-- populated by beacon link-spec -->

- specs/001-standardise-logging/
## ADRs

- [ADR-001](../../ADRs/ADR-001-stdlib-logging-over-console-libraries.md) — stdlib logging over colored console libraries
- [ADR-002](../../ADRs/ADR-002-nullhandler-pattern-for-library-loggers.md) — NullHandler pattern for library loggers

## Success criteria
- [x] `logger.setLevel(logging.DEBUG)` removed from all modules; log level controlled entirely by the host (ComfyUI or the user's logging config)
- [x] `logging.NullHandler()` added to the package root logger in `__init__.py`
- [x] All diagnostic `print()` calls converted to `logger.debug()` / `logger.info()` / `logger.error()` as appropriate
- [x] `colorama`, `termcolor`, and `rich` removed from runtime dependencies in `pyproject.toml` (they are only used for the now-deleted console-print logging)
- [x] A normal ComfyUI run produces zero output from this package unless the host enables DEBUG
- [x] Errors (template render failures, file-save failures, interrupt triggers) still surface at `ERROR` / `INFO` level
- [x] All existing tests pass; no new test failures introduced

## Non-goals
- Not adding a user-facing log-level toggle inside ComfyUI's UI
- Not changing node behaviour, output structure, or ComfyUI API contracts
- Not adding structured/JSON logging

## Notes
The `IS_CHANGED` and `update_widget` methods fire on every keystroke via the JS → aiohttp route. Any log call at INFO or above in these hot paths will be visible to the user. All calls in these hot paths must be DEBUG or removed.
