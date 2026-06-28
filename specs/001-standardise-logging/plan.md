# Implementation Plan: Standardise Node Logging

**Branch**: `001-standardise-logging` | **Date**: 2026-06-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-standardise-logging/spec.md`

## Summary

Remove all hardcoded log-level configuration and diagnostic `print()` calls from the three ComfyUI node modules (`format_string.py`, `random_choice.py`, `circuit_breaker.py`), replace them with correctly-levelled `logger.*` calls, add a `NullHandler` to the package root, and drop the three runtime dependencies (`colorama`, `termcolor`, `rich`) that exist solely to colour those now-deleted prints. The result is a well-behaved Python library that emits nothing by default and is fully controllable by the host logging configuration.

## Technical Context

**Language/Version**: Python 3.10+ (constrained by ComfyUI minimum; managed via `uv`)

**Primary Dependencies**:
- `jinja2` — template rendering (retained; unaffected by this change)
- `aiohttp` — ComfyUI web routes (retained; unaffected)
- `colorama`, `termcolor`, `rich` — **removed** (used only for coloured print() logging)
- Standard library: `logging` (already imported in `format_string.py`)

**Storage**: N/A

**Testing**: `pytest` via `uv run pytest`; `caplog` fixture for log-record assertions

**Target Platform**: ComfyUI custom-node environment (Python process); also importable in plain pytest without ComfyUI

**Project Type**: Python library / ComfyUI plugin

**Performance Goals**: `IS_CHANGED` and `update_widget` execute on every keystroke — zero stdout/stderr I/O is the target in the hot path

**Constraints**: Must not change any ComfyUI node API (INPUT_TYPES, RETURN_TYPES, FUNCTION, CATEGORY, NODE_CLASS_MAPPINGS). Must not break existing tests.

**Scale/Scope**: Three source files + `__init__.py` + `pyproject.toml`; ~30 call-sites changed.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|-----------|-------|--------|
| **ComfyUI Contract First** | No NODE_CLASS_MAPPINGS, RETURN_TYPES, INPUT_TYPES, or FUNCTION names change | ✅ PASS |
| **Sandbox All User-Supplied Code** | No change to Jinja2 SandboxedEnvironment usage | ✅ PASS |
| **Test-First (NON-NEGOTIABLE)** | New log-assertion tests written before implementation; existing tests confirmed passing | ✅ PASS — enforced in tasks |
| **Graceful Degradation Outside ComfyUI** | `comfy.*` guards unchanged; logging works without ComfyUI | ✅ PASS |
| **Simplicity — Function Before Class** | Removing code, not adding abstractions | ✅ PASS |
| **Fixed Output Positions** | No change to RETURN_TYPES/RETURN_NAMES structure | ✅ PASS |

No violations. Complexity Tracking section is omitted.

## Project Structure

### Documentation (this feature)

```text
specs/001-standardise-logging/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── contracts/
│   └── logging-contract.md   ← Phase 1 output (developer logging API)
└── tasks.md             ← Phase 2 output (/beacon:tasks)
```

### Source Code (affected files only)

```text
src/comfydv/
├── __init__.py          ← add NullHandler
├── format_string.py     ← remove setLevel; remove print() dump block; remove `from rich import print`; downgrade hot-path INFO→DEBUG
├── random_choice.py     ← replace print()+colorama/termcolor with logger.*; remove imports
└── circuit_breaker.py   ← add logger; replace bare print() with logger.debug()

tests/
└── test_logging.py      ← new: NullHandler, silence, error visibility, debug opt-in

pyproject.toml           ← remove colorama, termcolor, rich from [project.dependencies]
```
