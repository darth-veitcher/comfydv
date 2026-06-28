# ADR-001: Use stdlib logging instead of colored console output libraries

## Status

> Accepted

_Date:_ 2026-06-28
_Deciders:_ darth-veitcher

---

## Context

The initial implementation of comfydv used `colorama`, `rich`, and `termcolor` for
colored console output in `format_string.py` and `random_choice.py`. These libraries
were listed as runtime dependencies, meaning every ComfyUI installation that uses
comfydv would install them even though their sole purpose was developer debugging.

The visible symptom (GitHub issue #4) was 8 lines of diagnostic output printed to
the ComfyUI console on every keystroke in a FormatString node, because:
1. `logger.setLevel(logging.DEBUG)` was called unconditionally in the module, and
2. Hot-path methods (`IS_CHANGED`, `update_widget`) logged at INFO level.

ComfyUI is a plugin host. Any output comfydv writes to stdout is mixed with ComfyUI's
own output, making the console unusable during normal workflow editing.

## Decision

Remove `colorama`, `rich`, and `termcolor` as runtime dependencies. Replace all
`print(colored(...))`, `pprint(...)`, and `from rich import print` usage with calls
to `logging.getLogger(__name__)`. Debug output that was valuable for development is
preserved at `DEBUG` level so it reappears when the host opts in via
`logging.basicConfig(level=logging.DEBUG)` or equivalent.

## Consequences

**Easier:**
- The ComfyUI console is silent during normal workflow use.
- comfydv's runtime dependency footprint shrinks from 4 packages to 1 (`jinja2`).
- Debug traces are still available to developers who configure the `comfydv` logger.

**Harder / constrained:**
- Colored output is no longer available even in debug mode. Plain log records are
  less visually distinct than colored terminal output.

**Debt introduced:**
- None. The removed libraries had no purpose beyond developer diagnostics.

## Considered Alternatives

### Alternative A: Keep rich/colorama/termcolor but gate them behind a debug flag

**Why rejected:** Any debug flag adds configuration surface. The right solution for
a library is to use the logging system — callers configure it. Adding a bespoke
`COMFYDV_DEBUG=1` env var would be an undiscoverable one-off.

### Alternative B: Move colored output to dev-only dependency group

**Why rejected:** The `print()` calls write directly to stdout regardless of how the
package is installed. Moving the packages to `[dependency-groups].dev` would remove
them from the sdist/wheel but the import in the module-level code would then fail at
runtime. It does not solve the silent-during-normal-use requirement.

---

## Links

- Related spec: `specs/001-standardise-logging/`
- Related ADRs: [ADR-002](ADR-002-nullhandler-pattern-for-library-loggers.md)
