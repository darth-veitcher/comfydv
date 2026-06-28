# ADR-005: Ollama host configuration via OllamaClient node and OLLAMA_CLIENT socket type

## Status

> Accepted

_Date:_ 2026-06-28
_Deciders:_ darth-veitcher

---

## Context

The Ollama integration requires every node that contacts the Ollama REST API to
know the server's host URL (default: `http://localhost:11434`). There are three
reasonable strategies for distributing this configuration:

1. **Hard-code `localhost`** in every node — simple but inflexible; breaks for
   users running Ollama on a different host or port.
2. **Global settings / environment variable** — decouples nodes from each other
   but requires ComfyUI settings UI integration or env-var documentation.
3. **Config node pattern** — a dedicated `OllamaClient` node carries the host
   URL; other nodes accept it via a typed `OLLAMA_CLIENT` input socket. The
   connection is explicit and visible on the canvas.

The source repo (`comfyui-ollama-model-manager`) already uses the config-node
pattern with an `OllamaClient` node and custom `OLLAMA_CLIENT` type. This is
established and understood by users of the original package.

## Decision

The `OllamaClient` node is the single source of Ollama host configuration. It:
- Accepts a host URL string (widget, default `http://localhost:11434`).
- Outputs a typed `OLLAMA_CLIENT` connection handle.

All other Ollama nodes (`OllamaModelSelector`, `OllamaLoadModel`,
`OllamaUnloadModel`, `OllamaChatCompletion`) accept an `OLLAMA_CLIENT` input.
They MUST NOT hard-code a host URL or read it from environment variables.

The `OLLAMA_CLIENT` type is registered as a custom ComfyUI type (a string
subtype at runtime, but typed to prevent accidental wiring to unrelated nodes).

This pattern is orthogonal to ComfyUI's global settings and does not preclude
a future global-settings integration (the escape hatch is: make `OllamaClient`
read from settings if the URL widget is left blank).

## Consequences

**Easier:**
- The connection configuration is visible on the canvas — users can see which
  Ollama server a group of nodes points to.
- Multiple `OllamaClient` nodes can coexist (e.g. local + remote Ollama) — users
  wire different clients to different node groups.
- Changing the host is one edit on one node, not a global setting change.

**Harder / constrained:**
- Every workflow that uses Ollama nodes must include at least one `OllamaClient`
  node. This adds one node to the minimum workflow footprint.
- The `OLLAMA_CLIENT` socket type means `OllamaModelSelector` etc. cannot be
  used without the client node — there is no "quick" mode that skips it.

**Debt introduced:**
- None. The pattern matches the established design in the source repo and is
  consistent with how other ComfyUI integrations (e.g. API key config nodes)
  handle credentials/connection config.

## Considered Alternatives

### Alternative A: Hard-code localhost in every node

**Why rejected:** Breaks users running Ollama on a non-default host/port.
Non-configurable without source changes.

### Alternative B: Read host from ComfyUI global settings or environment variable

**Why rejected:** Requires integrating with ComfyUI's settings API (a wider
scope change) or undiscoverable env-var documentation. The config-node pattern
is discoverable on the canvas and explicit in the workflow graph.

### Alternative C: Add a host widget to every node that needs it

**Why rejected:** Violates DRY — the user sets the same address N times. If the
host changes, every node must be updated individually.

---

## Links

- Related spec: `specs/006-ollama-model-integration/`
- Parent epic: `project-management/Roadmap/epics/ollama-integration.md`
- Related ADRs: [ADR-003](ADR-003-requirements-txt-authoring-policy.md), [ADR-004](ADR-004-aiohttp-over-httpx-for-ollama.md)
