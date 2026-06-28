# Epic: ComfyUI UX Polish & Manager Compatibility

## Status
Active  — started 2026-06-28

## Why now
A codebase audit (2026-06-28) surfaced three categories of defects that collectively prevent comfydv from being correctly installed via ComfyUI Manager and degrade the user experience in every ComfyUI session:

1. **Installation is broken**: `requirements.txt` contains a bare `.` and lists removed packages (`colorama`, `termcolor`) rather than the actual runtime dep (`jinja2`). ComfyUI Manager runs `pip install -r requirements.txt` after cloning — this silently misinstalls the node. The package is also not registered in Manager's `custom-node-list.json` so it cannot be found via the Manager UI at all.

2. **Core UX bugs every user encounters**: The FormatString template field fires a full server round-trip and clears all output connections on every keystroke (no debounce). Switching templates drops wired connections. User feedback is delivered via browser `alert()` dialogs. Node IDs are mismatched between JS (prefixed `format_string_<n>`) and Python (bare `<n>`), so server-side config lookup always returns empty.

3. **Correctness bugs in node logic**: `FormatString.update_widget` mutates class-level `RETURN_TYPES`/`RETURN_NAMES`/`OUTPUT_IS_LIST`, meaning two FormatString nodes in the same workflow corrupt each other's output metadata. `RandomChoice.IS_CHANGED` calls the real `random_choice` method to determine change (consuming random state). seed=0 is treated as "no seed" due to falsy check, making the default value non-deterministic. `CircuitBreaker.trigger` is hardcoded to `IMAGE`, preventing use at non-image stages.

4. **Metadata drift**: `pyproject.toml` `description` is still the placeholder "Add your description here". A `comfydv = "comfydv:main"` script entry is declared but no `main()` function exists — any `pip install` would create a broken CLI entry point. `dynamic.js` references `ToJSON`/`To JSON` nodes that don't exist. `src/comfydv/README.md` describes a "Model Unloader" node that was never implemented.

## Dependencies
_None — this epic is self-contained and can start immediately._

## Specs

<!-- populated by beacon link-spec -->

- specs/002-manager-compatible-install-requirements-txt-and-custom-node-list-registration/
- specs/003-formatstring-frontend-ux-debounce-connection-migration-node-id-parity-toast-feedback/
- specs/004-node-logic-correctness-per-instance-formatstring-schema-randomchoice-determinism-circuitbreaker-any-type/
- specs/005-metadata-cleanup-pyproject-description-scripts-dead-code-removal-tooltips-category-consistency/
## ADRs

- [ADR-003](../../ADRs/ADR-003-requirements-txt-authoring-policy.md) — hand-authored requirements.txt as curated subset of pyproject.toml

## Success criteria

- [ ] `requirements.txt` at repo root lists only actual runtime dependencies (`jinja2>=3.1.6`), is hand-authored not `uv export`-generated, and a `uv sync` + Manager-simulated install succeeds
- [ ] comfydv is submitted to / listed in `ltdrdata/ComfyUI-Manager`'s `custom-node-list.json`
- [ ] FormatString template input is debounced (≥ 300 ms) so output connections are not dropped while a user is still typing
- [ ] FormatString output slots are updated via `removeOutput`/`addOutput` with connection migration rather than wiping `this.outputs.length = 0`
- [ ] FormatString node ID is consistent between JS and Python (no `format_string_` prefix mismatch)
- [ ] User feedback (load state, errors) uses ComfyUI toast API, not `alert()`
- [ ] `FormatString.update_widget` stores per-node return-type metadata on instances or a node-keyed dict, not on the class itself — two FormatString nodes in the same workflow produce independent output schemas
- [ ] `RandomChoice.IS_CHANGED` does not call the actual `random_choice` method; uses a hash of the seed + input count instead
- [ ] `RandomChoice` seed=0 produces a deterministic, reproducible output (sentinel for "random" is -1 or an explicit widget toggle)
- [ ] `CircuitBreaker.trigger` accepts `any_type` so it can be placed anywhere in a graph, not only after IMAGE nodes
- [ ] `pyproject.toml` `description` is a real sentence; the broken `[project.scripts]` entry is removed
- [ ] Dead code and stale references are removed: `ToJSON`/`To JSON` from `dynamic.js`, "Model Unloader" from `src/comfydv/README.md`
- [ ] `aiohttp` is moved from dev dependencies to production dependencies (it is imported unconditionally at module level)
- [ ] All three nodes have `"tooltip"` metadata on each input
- [ ] CATEGORY is consistent across all three nodes (single submenu)
- [ ] `beacon doctor --strict` passes on `main` after each spec merges

## Non-goals

- Implementing new nodes or new node capabilities beyond fixing the above
- Migrating to ComfyUI Registry / pip-installable wheel (deferred; separate epic once git-clone path is solid)
- Adding structured/JSON logging (covered by logging-modernisation epic)
- Frontend redesign beyond the identified UX bugs
- Full aiohttp route integration tests (coverage gap noted; out of scope here)

## Notes

**Audit source**: Two parallel subagent audits run 2026-06-28:
- Codebase audit: node definitions, JS frontend, package structure, UI/UX issues, known bugs
- ComfyUI Manager requirements: installation channels, gap analysis, MVPs per channel

**JS architecture note**: Both JS files use the `app.registerExtension` + `beforeRegisterNodeDef` pattern correctly. The debounce fix should introduce a `debounce(fn, delay)` utility inline or imported from a shared module — do not reach for a npm dependency.

**Class-mutation fix strategy**: `RETURN_TYPES`, `RETURN_NAMES`, `OUTPUT_IS_LIST` should become per-node-instance attributes. ComfyUI reads these from the class at registration time but at execution time it uses the values serialised in the workflow JSON. The JS side is authoritative at execution time — the Python class attributes only need to match at load/registration. Consider moving dynamic output schema into `node_configs` and having the Python execution method derive its return signature from the node config rather than class attrs.

**Two-`__init__.py` risk**: The git-clone entry point at `/comfydv/__init__.py` re-exports from `src/comfydv`. Adding a new node requires editing both files. A test asserting `root.NODE_CLASS_MAPPINGS == src.NODE_CLASS_MAPPINGS` should be added to prevent silent drift.
