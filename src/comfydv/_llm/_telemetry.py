"""Telemetry and phone-home behaviour off by default (ADR-014).

comfydv runs inside a user's ComfyUI process and talks only to servers the
user wired in. The libraries under ``comfydv._llm`` ship with a few
behaviours that report, announce or call out on their own. Each is switched
off here unless the user has already set it:

- **FastMCP** (``pydantic-ai-slim[mcp]``):
  - ``FASTMCP_TELEMETRY_MODE=off``: no OpenTelemetry spans, and no trace
    context injected into request ``_meta``, so nothing correlating a run
    is sent to external MCP servers.
  - ``FASTMCP_CHECK_FOR_UPDATES=off``: no PyPI version check when a server
    banner is shown (comfydv's own MCP servers run standalone).
  - ``FASTMCP_SHOW_SERVER_BANNER=false``: no stdout banner (ADR-001).
- **pydantic-ai**: ``PYDANTIC_AI_NO_BANNER=1`` suppresses the first-run
  stdout banner that advertises a hosted observability service (ADR-001).
  Agent instrumentation is already off by default (``Agent.instrument_all``
  is never called by comfydv).
- **Monty** (``pydantic-monty``): telemetry is opt-in only, via
  ``pydantic_monty.instrument_telemetry()``, which comfydv never calls.

Everything uses ``os.environ.setdefault``, so an explicit user setting always
wins: that is the opt-in path. Environment variables, rather than library
attributes, mean nothing here imports pydantic-ai or FastMCP, so applying the
defaults costs nothing on code paths that never use them. They must be in
place before FastMCP is first imported, because it reads its settings once
at import time; ``comfydv/_llm/__init__.py`` calls ``apply()`` before any
``_llm`` submodule can import either library.

These are process-wide: another ComfyUI node pack that uses FastMCP or
pydantic-ai in the same process sees the same defaults, unless the user (or
that pack) set the variables first.
"""

import os

TELEMETRY_DEFAULTS: dict[str, str] = {
    "FASTMCP_TELEMETRY_MODE": "off",
    "FASTMCP_CHECK_FOR_UPDATES": "off",
    "FASTMCP_SHOW_SERVER_BANNER": "false",
    "PYDANTIC_AI_NO_BANNER": "1",
}


def apply() -> None:
    """Set each default unless the user already chose a value."""
    for name, value in TELEMETRY_DEFAULTS.items():
        os.environ.setdefault(name, value)
