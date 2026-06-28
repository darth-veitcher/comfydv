# ADR-002: NullHandler pattern for the comfydv package root logger

## Status

> Accepted

_Date:_ 2026-06-28
_Deciders:_ darth-veitcher

---

## Context

comfydv is a ComfyUI plugin — a library loaded into a host application. Python's
logging documentation explicitly states that libraries should not configure logging
(no `basicConfig`, no `setLevel`, no `StreamHandler` added to the root logger),
because doing so hijacks the host application's logging configuration.

The initial code violated this in two ways:
1. `logger.setLevel(logging.DEBUG)` was called unconditionally in `format_string.py`,
   forcing all debug records through even when the host had not opted in.
2. No `NullHandler` was registered, so if the host application had not configured
   logging, Python's "last resort" handler would write WARNING+ records to stderr.

## Decision

Follow PEP 282 and the Python logging HOWTO's recommendation for library code:

1. Add `logging.getLogger(__name__).addHandler(logging.NullHandler())` to
   `src/comfydv/__init__.py`. This suppresses all output when the host has not
   configured logging, preventing spurious stderr noise.
2. Remove every `logger.setLevel(...)` call from module-level code. Level is the
   host's responsibility.
3. Use `logging.getLogger(__name__)` in every module (hierarchy rooted at `comfydv`).

Hosts that want debug output from comfydv add one line:
```python
logging.getLogger("comfydv").setLevel(logging.DEBUG)
```

## Consequences

**Easier:**
- comfydv is a well-behaved library citizen: zero console output by default.
- The host controls verbosity without any comfydv-specific API.
- All existing log call sites are preserved — turning on debug gives full traces.

**Harder / constrained:**
- Developers who previously relied on automatic stdout output during ComfyUI sessions
  must now configure the logger explicitly to see debug traces.

**Debt introduced:**
- None.

## Considered Alternatives

### Alternative A: Remove all logging, use only print for visible output

**Why rejected:** print() cannot be suppressed without patching sys.stdout. A
logging call at DEBUG costs essentially nothing when the level gate is not open.
Removing logging would destroy the debug-mode capability.

### Alternative B: Write a comfydv-specific debug flag (env var or config file)

**Why rejected:** Reinvents the logging system. Python's logging hierarchy already
provides per-package level control. A bespoke flag adds undiscoverable configuration
surface with the same semantics.

---

## Links

- Related spec: `specs/001-standardise-logging/`
- Related ADRs: [ADR-001](ADR-001-stdlib-logging-over-console-libraries.md)
- External reference: https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library
