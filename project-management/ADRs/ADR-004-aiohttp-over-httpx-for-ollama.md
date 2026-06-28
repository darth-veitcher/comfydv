# ADR-004: Use aiohttp for Ollama HTTP communication instead of httpx

## Status

> Accepted

_Date:_ 2026-06-28
_Deciders:_ darth-veitcher

---

## Context

The Ollama model integration requires async HTTP calls to the Ollama REST API
(`/api/tags`, `/api/load`, `/api/generate`, `/api/chat`). The source repository
(`darth-veitcher/comfyui-ollama-model-manager`) uses `httpx>=0.28.1` for this
purpose.

comfydv is installed as a ComfyUI custom node. ComfyUI's own web server is built
on `aiohttp`, which is therefore always present in the ComfyUI environment — it
is a guaranteed transitive dependency. ADR-003 establishes that `requirements.txt`
should list only runtime deps **not** already provided by ComfyUI; adding `httpx`
would add a new network dependency for a use case (`aiohttp`) already satisfied.

`httpx` and `aiohttp` both support async HTTP GET/POST with JSON. The Ollama API
uses simple JSON over HTTP — no streaming multipart, no HTTP/2 negotiation, no
features that require `httpx` specifically. The complexity difference between the
two clients for this task is negligible.

## Decision

Use `aiohttp` for all Ollama HTTP communication. Do **not** add `httpx` to
`pyproject.toml [project.dependencies]` or `requirements.txt`.

All async calls to the Ollama API (`/api/tags`, `/api/load`, `/api/generate`,
`/api/chat`) use `aiohttp.ClientSession`.

## Consequences

**Easier:**
- No new dependency needed — `aiohttp` is already in every ComfyUI environment.
- `requirements.txt` unchanged (per ADR-003, no new entry required).
- One fewer package to audit, update, or pin.

**Harder / constrained:**
- `aiohttp` has a slightly more verbose API than `httpx` for simple JSON requests
  (must use `async with session.post(...) as resp:` pattern). This is a minor
  ergonomic cost.
- If ComfyUI ever removes `aiohttp` from its dep tree (unlikely), this decision
  would need revisiting.

**Debt introduced:**
- None.

## Considered Alternatives

### Alternative A: Use `httpx` (as in the source repo)

**Why rejected:** Adds a new runtime dep for functionality `aiohttp` already provides.
Violates the spirit of ADR-003 (only add deps ComfyUI doesn't already provide).
`httpx` also pins a minimum version, creating a potential conflict with any httpx
already installed in the user's environment.

### Alternative B: Use `urllib.request` (stdlib)

**Why rejected:** `urllib.request` is synchronous and not suitable for ComfyUI's
async node execution model. Using it would require `asyncio.run()` inside async
code, which causes event-loop conflicts.

---

## Links

- Related ADR: [ADR-003](ADR-003-requirements-txt-authoring-policy.md)
- Parent epic: `project-management/Roadmap/epics/ollama-integration.md`
- Related spec: `specs/006-ollama-model-integration/`
