# comfydv Constitution

## Core Principles

### I. ComfyUI Contract First
Every node **must** expose `INPUT_TYPES`, `RETURN_TYPES`, `RETURN_NAMES`, `FUNCTION`, and `CATEGORY` to comply with ComfyUI's node registration contract. `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` in the package `__init__.py` are the only install-time interface — nothing else. Do not require changes to ComfyUI itself.

### II. Sandbox All User-Supplied Code
Any template or expression evaluated at runtime from user input **must** run inside Jinja2's `SandboxedEnvironment` or equivalent. Plain `eval()` or `exec()` on user strings is forbidden. The `additional_context` dict is the only way to expose utilities to templates.

### III. Test-First (NON-NEGOTIABLE)
Write the test before writing the implementation. Tests **must** pass without a live ComfyUI instance — all `comfy.*` and `server.*` imports are runtime-guarded (`if "comfy" in sys.modules`). The test suite runs via `uv run pytest`. Red → Green → Refactor; do not commit red tests.

### IV. Graceful Degradation Outside ComfyUI
Modules imported outside ComfyUI (e.g., in tests or CI) must log a warning and continue loading rather than raising an `ImportError`. The node's core logic (template parsing, key extraction, formatting) must be independently testable without any ComfyUI dependency.

### V. Simplicity — Function Before Class
Prefer module-level functions over class methods where there is no shared state. Prefer a single script over a service. Use classes only when ComfyUI's node registration pattern requires them. No premature abstractions; three similar lines beat a helper no one asked for.

### VI. Fixed Output Positions
Primary outputs (`formatted_string`, `saved_file_path`) **must** always occupy positions 0 and 1 in `RETURN_TYPES`/`RETURN_NAMES`. Variable pass-through outputs follow at positions 2+. This contract, once established for a node, is immutable — changing it breaks existing workflows silently.

## Quality Gates

Before any bullet is considered done:

```bash
uv run ruff check --fix && uv run ruff format
uv run ty check
uv run pytest
beacon doctor --strict
```

All four must be green. No exceptions.

## Governance

This constitution supersedes style preferences and any CLAUDE.md defaults where they conflict. Amendments require an ADR entry in `project-management/ADRs/` with a rationale and migration note. All PRs are checked against this constitution before merge.

**Version**: 1.0.0 | **Ratified**: 2026-06-28 | **Last Amended**: 2026-06-28
