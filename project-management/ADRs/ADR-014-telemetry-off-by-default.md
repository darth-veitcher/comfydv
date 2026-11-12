# ADR-014: Telemetry and phone-home behaviour off by default

## Status

> Accepted

_Date:_ 2026-11-12
_Deciders:_ darth-veitcher

---

## Context

The maintainer asked for all telemetry to be switched off by default. comfydv runs inside a user's
ComfyUI process and should contact only the servers wired into the graph: Ollama, llama-server,
SearXNG, MCP servers.

The pydantic-ai 2.68 upgrade (ADR-013) brought in FastMCP, the MCP SDK, Monty and OpenTelemetry's
API. An audit of the installed stack (2026-11-12) found:

| Library | Behaviour | Default upstream |
|---|---|---|
| FastMCP 4.1 | OpenTelemetry spans, plus **trace context injected into MCP request `_meta`**, which is sent to external servers | on (`telemetry_mode="native"`) |
| FastMCP 4.1 | **PyPI version check** when a server banner is shown | on (`check_for_updates="stable"`) |
| FastMCP 4.1 | stdout server banner | on |
| pydantic-ai 2.68 | stdout first-run banner advertising a hosted observability service | on |
| pydantic-ai 2.68 | Agent instrumentation | **off** (`Agent._instrument_default = False`) |
| Monty 1.6 | OpenTelemetry instrumentation | **off**; opt-in only via `instrument_telemetry()` |
| pydantic-ai-harness | `PostHog` capability | Not telemetry: an opt-in connector to PostHog's MCP server |

No hardcoded analytics endpoints were found elsewhere. OpenTelemetry spans are no-ops without an
SDK and exporter, but FastMCP's context propagation and version check still reach the network.

## Decision

Apply defaults in one module, `comfydv/_llm/_telemetry.py`, which `comfydv/_llm/__init__.py`
calls before any submodule can import pydantic-ai or FastMCP:

```
FASTMCP_TELEMETRY_MODE=off
FASTMCP_CHECK_FOR_UPDATES=off
FASTMCP_SHOW_SERVER_BANNER=false
PYDANTIC_AI_NO_BANNER=1
```

The defaults are set with `os.environ.setdefault`, so **an explicit user setting always wins**;
that is the opt-in path, documented in the README. Environment variables rather than library
attributes because FastMCP reads its settings once at import time, and because this way nothing is
imported eagerly (verified by test). comfydv never calls `Agent.instrument_all()` or
`pydantic_monty.instrument_telemetry()`.

Any new dependency that reports, announces or calls out on its own gets its off-switch added to
`TELEMETRY_DEFAULTS`, with a test.

## Consequences

**Easier:**
- One place to audit and extend. Tests prove each default applies, that user values win, that
  FastMCP and pydantic-ai observe them, and that applying them imports nothing heavy.
- Replaces the earlier `pydantic_ai.BANNER_ENABLED = False` assignment and its `ty` suppression.

**Harder / constrained:**
- **Process-wide.** Another node pack using FastMCP or pydantic-ai in the same ComfyUI process
  inherits these defaults, unless the user or that pack set the variables first. This is accepted
  (the change only removes outbound behaviour) and documented.
- If FastMCP is imported before `comfydv._llm` (by another node pack loaded first), FastMCP's
  settings are already fixed and the env defaults don't affect it. Users who need a guarantee should
  set the variables before starting ComfyUI.
- Upstream can add new behaviours, or rename variables, on upgrade. The exact pins (ADR-013) plus
  the import-order tests catch a rename; a new behaviour needs a re-audit on each upgrade.

## Considered Alternatives

### Alternative A: Set library attributes (`fastmcp.settings.telemetry_mode = "off"` and so on)

**Why rejected:** It forces eager imports of FastMCP and pydantic-ai on every comfydv load, and it
can't tell a user's explicit choice from the upstream default, so it would override opt-ins.

### Alternative B: Rely on upstream defaults

**Why rejected:** FastMCP's defaults propagate trace context to external MCP servers and check PyPI.

---

## Links

- Related ADRs: [ADR-001](ADR-001-stdlib-logging-over-console-libraries.md) (silent by default), [ADR-013](ADR-013-monty-sandbox-code-mode-and-skill-scripts.md) (the upgrade that introduced these libraries)
- Code: `src/comfydv/_llm/_telemetry.py`; tests: `tests/test_llm_telemetry_defaults.py`
