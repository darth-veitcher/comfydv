# Research: Standardise Node Logging

## Python Library Logging — Best Practices

**Decision**: Add `logging.NullHandler()` to the package root logger in `__init__.py`; never set level or add handlers inside the library.

**Rationale**: PEP 282 and the Python logging HOWTO state explicitly that libraries should add only a `NullHandler` to their top-level logger. This means:
- A host application with no logging configuration sees nothing (NullHandler swallows all records)
- A host that configures a handler + level gets exactly what it asks for
- The library never fights the host for control of output

**Alternatives considered**:
- Leaving `logger.setLevel(logging.DEBUG)` — rejected; this is the root cause of issue #4 and violates the library contract
- Adding a `StreamHandler` with a flag to disable it — rejected; unnecessary complexity, still breaks the host's control

---

## Hot-Path Log Level

**Decision**: All log calls inside `IS_CHANGED` and `update_widget` (and their aiohttp route handler) are capped at `DEBUG`.

**Rationale**: Both methods execute synchronously on every keystroke in the ComfyUI UI. Any `INFO` or higher call in these paths goes to whatever handlers the host has configured at INFO+. In a standard ComfyUI session that means console output on every keypress — exactly the reported bug. `DEBUG` is the correct level for trace/diagnostic information a developer explicitly opts into.

**Alternatives considered**:
- Removing all logging from `IS_CHANGED` entirely — acceptable but leaves no debug path; DEBUG is preferable
- Adding a module-level flag to suppress — rejected; that's re-inventing the logging framework

---

## `print()` in Library Code

**Decision**: All `print()` calls used for diagnostic output are replaced with `logger.*` at the appropriate level. `from rich import print` override is removed.

**Rationale**: `print()` writes unconditionally to stdout and cannot be suppressed by the host's logging configuration. Shadowing the built-in `print` via `from rich import print` is additionally dangerous because it silently changes behaviour for every `print()` call in the module, making it harder to audit what's going to stdout.

Correct mapping:
| Original call | Replacement |
|---|---|
| `print(f"[FormatString Node {id}] Output: ...")` | `logger.debug(...)` |
| `print(colored("\nRandom Choice", ...))` | `logger.debug("RandomChoice: executing")` |
| `print(colored("Got these inputs:", ...))` | `logger.debug("RandomChoice inputs: %s", ...)` |
| `print(colored(f"Chose: {choice}", ...))` | `logger.debug("RandomChoice selected: %s", choice)` |
| `print("Circuit Breaker triggered")` | `logger.debug("CircuitBreaker: interrupt triggered")` |
| `print(f"Error loading node state: {e}")` | `logger.error("Failed to load node state from %s: %s", file_path, e)` |

---

## Removing `colorama`, `termcolor`, `rich`

**Decision**: All three packages are removed from `[project.dependencies]` in `pyproject.toml`.

**Rationale**: After removing the `print()`-based logging, grep confirms none of these packages are imported anywhere else in the package. They are dead dependencies that add installation weight and version-pin surface area for no benefit.

```
colorama  — used only in random_choice.py: just_fix_windows_console()
termcolor — used only in random_choice.py: colored()
rich      — used in format_string.py: from rich import print
            used in random_choice.py: from rich.pretty import pprint
```

All uses are exclusively in the logging/print blocks being removed.

**Alternatives considered**:
- Keeping `rich` as a dev-only dependency — rejected; no remaining use case even in dev
- Keeping `colorama` for Windows console compatibility — rejected; the underlying `print()` calls that needed it are gone

---

## `% formatting` vs f-strings in log calls

**Decision**: Use `%`-style formatting for log calls (`logger.debug("value: %s", x)`), not f-strings.

**Rationale**: The logging framework only interpolates the message string if a handler actually processes the record. With f-strings, the string is always constructed even if the log record is discarded (e.g. by NullHandler). For hot-path calls (every keystroke), this matters. `%`-style is the convention recommended in the Python logging docs.
