# Implementation Plan: Manager-Compatible Install

**Branch**: `002-manager-install` | **Date**: 2026-06-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-manager-compatible-install-requirements-txt-and-custom-node-list-registration/spec.md`

## Summary

Fix comfydv's packaging so ComfyUI Manager can install it correctly: replace the broken
auto-generated `requirements.txt` with a hand-authored one listing only `jinja2>=3.1.6`,
promote `aiohttp` from dev-only to production dependencies in `pyproject.toml`, correct the
stale `@description` metadata in `__init__.py`, and submit a PR to
`ltdrdata/ComfyUI-Manager` to list the package in Manager's search UI.

## Technical Context

**Language/Version**: Python 3.11 (`pyproject.toml` target), plain text (`requirements.txt`), JSON (`custom-node-list.json` PR)

**Primary Dependencies**:
- `jinja2>=3.1.6` — sole runtime dep not bundled by ComfyUI
- `aiohttp>=3.9.0` — provided by ComfyUI's own environment; must be listed in `pyproject.toml [project.dependencies]` for pip-install correctness but **not** in `requirements.txt` (ComfyUI already satisfies it for git-clone users)

**Storage**: N/A — no data storage changes

**Testing**: `uv run pytest` — new test asserting `requirements.txt` correctness and `@description` accuracy

**Target Platform**: Any environment where ComfyUI is installed; CI (GitHub Actions / local)

**Project Type**: ComfyUI custom node plugin; packaging/configuration spec

**Performance Goals**: N/A — install is a one-time operation

**Constraints**: `requirements.txt` must be parseable by `pip install -r`; the ComfyUI Manager PR must follow the exact JSON schema of `custom-node-list.json`

**Scale/Scope**: 3 files changed, 1 external PR opened; no new source files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. ComfyUI Contract First | ✅ Pass | No changes to node registration or `NODE_CLASS_MAPPINGS` |
| II. Sandbox All User-Supplied Code | ✅ Pass | N/A — no user-input evaluation changes |
| III. Test-First (NON-NEGOTIABLE) | ✅ Pass | Tests written before implementation (TDD pairs in tasks.md) |
| IV. Graceful Degradation Outside ComfyUI | ✅ Pass | Fix improves this — correct deps mean clean import outside ComfyUI |
| V. Simplicity — Function Before Class | ✅ Pass | Pure configuration changes; no new abstractions |
| VI. Fixed Output Positions | ✅ Pass | N/A — no output schema changes |

No violations. No Complexity Tracking table needed.

## Project Structure

### Documentation (this feature)

```text
specs/002-manager-compatible-install-requirements-txt-and-custom-node-list-registration/
├── spec.md         ✅ done
├── plan.md         ✅ this file
├── research.md     ✅ inlined below (no open questions)
└── tasks.md        ← /beacon:tasks next
```

### Source Code (repository root)

```text
requirements.txt          ← rewrite (FR-001, FR-002)
pyproject.toml            ← move aiohttp to [project.dependencies] (FR-003)
__init__.py               ← update @description (FR-005)
tests/test_packaging.py   ← new test file (constitution III)
```

External artefact (not in this repo):
```
ltdrdata/ComfyUI-Manager / custom-node-list.json  ← PR (FR-004)
```

## Research

### Decision 1: What belongs in `requirements.txt` vs `pyproject.toml`

**Context**: Two separate distribution paths exist: git-clone (ComfyUI Manager) and pip install. They have different dependency environments.

**Decision**: `requirements.txt` lists only deps **not already provided by ComfyUI's own environment**. ComfyUI depends on `aiohttp` itself, so it is always present for git-clone users. Only `jinja2>=3.1.6` goes in `requirements.txt`.

`pyproject.toml [project.dependencies]` lists **all** production runtime deps including `aiohttp>=3.9.0`, for correctness when the package is pip-installed outside a ComfyUI environment.

**Rationale**: Avoids version conflicts from double-installing `aiohttp` in Manager's pip step; keeps `requirements.txt` minimal and correct.

**Alternatives considered**:
- List `aiohttp` in `requirements.txt` too → redundant, and if versions conflict with ComfyUI's pinned version, Manager install silently downgrades ComfyUI's server
- Remove `aiohttp` from `pyproject.toml` entirely → correct for git-clone but breaks `pip install comfydv` in standalone environments

### Decision 2: `aiohttp` version constraint

**Decision**: `aiohttp>=3.9.0` — matches the floor ComfyUI itself uses. No upper bound (semver convention for libraries).

**Alternatives considered**: Pinning to `==3.9.x` would prevent upgrades when ComfyUI upgrades its own aiohttp.

### Decision 3: `custom-node-list.json` entry format

**Decision**: Follow the exact schema used by existing entries. Required fields:
```json
{
  "author": "Darth Veitcher",
  "title": "Comfy DV Nodes",
  "reference": "https://github.com/darth-veitcher/comfydv",
  "files": ["https://github.com/darth-veitcher/comfydv"],
  "install_type": "git-clone",
  "description": "...",
  "nodename": ["Format String (Python f-strings)", "Random Choice", "Circuit Breaker"]
}
```

**Rationale**: Manager parses this exact structure. `install_type: "git-clone"` is the standard path; `files` contains the repo URL for Manager to clone.

### Decision 4: `@description` replacement text

**Decision**: Replace the stale description with one that names only the three existing nodes and their purpose, removing the "model memory management" / "Model Unloader" reference.

**New text**: `"Quality of life ComfyUI nodes: dynamic string formatting with Python f-strings or Jinja2 templates, seed-controlled random input selection, and workflow circuit-breaker for conditional queue interruption."`

## Contracts

No external API contracts to define — this spec touches only packaging metadata and a
third-party JSON registry. The `requirements.txt` format is dictated by pip (no new
contract to author).

## Docker Compose Test Harness

A CPU-only ComfyUI environment is needed to verify SC-001 (deps install cleanly)
and SC-003 (nodes appear in the menu after install) without a GPU. This is deliverable
alongside the packaging fixes in this spec.

**Approach**: `docker-compose.yml` at the repo root with a single `comfyui` service:
- Base image: `python:3.11-slim` (or a community ComfyUI CPU image if one exists and is stable)
- Startup: clone / install ComfyUI CPU-only, then symlink/copy `comfydv` into
  `custom_nodes/`, run `pip install -r requirements.txt`, start ComfyUI server
- No GPU required: `--cpu-only` flag or `torch` CPU wheel
- Health check: `curl http://localhost:8188/` returns 200 → nodes loaded successfully
- Used by: developers testing install changes locally; future CI smoke test

**Constraints**: The harness must start in under 3 minutes on a developer laptop
(no model downloads; only the ComfyUI server + custom node registration). Model weights
are intentionally excluded — the goal is testing node registration and import, not
inference.

This is tracked as a dedicated task pair (T050-T / T050-I) in tasks.md.

## ADR Candidates

The following decision is cross-cutting (applies to all future specs, not just this one)
and warrants an ADR in the parent epic:

- **`requirements.txt` authoring policy**: hand-authored subset of `pyproject.toml` deps excluding ComfyUI-provided packages. This policy applies to every future PR that adds a runtime dependency. Recommend adding as `ADR-003` before closing this spec.
