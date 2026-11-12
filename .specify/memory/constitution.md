# comfydv Constitution

## Core Principles

### I. ComfyUI Contract First

- Each node MUST define `INPUT_TYPES`, `RETURN_TYPES`, `RETURN_NAMES`, `FUNCTION` and `CATEGORY`.
  Reason: ComfyUI registers a node only when it has all five.
- `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` in the package `__init__.py` MUST be the
  only install-time interface. Reason: ComfyUI reads nothing else when it loads a node pack.
- A change MUST NOT need a change to ComfyUI itself. Reason: users run an unmodified ComfyUI.

### II. Sandbox All User-Supplied Code

- A template or an expression from user input MUST run in Jinja2's `SandboxedEnvironment`, or in
  an equal sandbox. Reason: a shared workflow must not run code on the computer that opens it.
- Code MUST NOT call `eval()` or `exec()` on user text. Reason: both run any code without limits.
- The `additional_context` dict MUST be the only way to give utilities to templates. Reason: one
  place makes it possible to review what a template can reach.

### III. Test-First (NON-NEGOTIABLE)

- Write the test before the implementation: red, then green, then refactor. Reason: a test that
  is written first proves the behaviour, not the code that already exists.
- A commit MUST NOT contain a failing test. Reason: a red suite hides each new failure.
- Tests MUST pass without a live ComfyUI process, so code MUST guard each `comfy.*`, `server.*`
  and `folder_paths` import (`if "comfy" in sys.modules`). Reason: CI and contributors have no ComfyUI.
- `uv run pytest` MUST run the suite. Reason: one command gives the same result for each person.

### IV. Graceful Degradation Outside ComfyUI

- A module that loads outside ComfyUI MUST log a warning and continue. It MUST NOT raise an
  `ImportError`. Reason: tests, docs builds and other tools import the package without ComfyUI.
- The core logic of a node (template parsing, key extraction, formatting) MUST be testable with no
  ComfyUI dependency. Reason: the logic must be testable in isolation.

### V. Simplicity — Function Before Class

- Use a module-level function when there is no shared state. Reason: a function is simpler to
  read and to test than a class.
- Use a class only when ComfyUI's node registration needs it. Reason: extra structure adds cost.
- Use a single script before a service. Reason: a script has fewer parts that can fail.
- Code MUST NOT add an abstraction before a second use needs it. Reason: three similar lines
  cost less than a helper that nobody asked for.

### VI. Fixed Output Positions

- The primary outputs (`formatted_string`, `saved_file_path`) MUST be at positions 0 and 1 of
  `RETURN_TYPES` and `RETURN_NAMES`. Variable pass-through outputs MUST follow from position 2.
  Reason: saved workflows connect outputs by position.
- A change MUST NOT move an output that a released node already has. Reason: a moved output
  connects saved workflows to the wrong socket, and ComfyUI gives no error.

### VII. Documentation for People and for Agents

- `README.md`, `docs/`, `AGENTS.md` and the project artefacts (ADRs, epics, specs, plans, tasks
  and this constitution) MUST follow `docs/WRITING.md`. Reason: one standard (ASD-STE100
  Simplified Technical English and the project rules) makes each document clear to each reader.
- A change to behaviour that a user can see MUST change `README.md` or `docs/` in the same pull
  request. Reason: documentation that comes later is often wrong or missing.
- `beacon docs check` and `beacon doctor --strict` MUST pass. Reason: they find the mechanical
  faults before a review.
- A review MUST check the words, with the `beacon-docs-reviewer` agent. Reason: the check cannot
  read the STE dictionary.

## Quality Gates

All four gates MUST pass before a bullet is done. Reason: a bullet that does not pass them is not
ready to ship.

```bash
uv run ruff check --fix && uv run ruff format
uv run ty check
uv run pytest
beacon doctor --strict
```

`beacon doctor --strict` includes the documentation check of Article VII.

## Governance

- This constitution MUST win when it conflicts with a style preference or a `CLAUDE.md`
  default. Reason: the plan gate needs one source of rules.
- An amendment MUST have an ADR in `project-management/ADRs/` with a rationale and a migration
  note. Reason: the ADR records why each rule changed.
- Each pull request MUST pass a check against this constitution before merge. Reason: a rule
  that nobody checks has no effect.
- The version MUST follow semantic versioning. Remove or redefine a principle: MAJOR. Add a
  principle or expand one: MINOR. Change only the wording: PATCH.

**Version**: 1.1.0 | **Ratified**: 2026-06-28 | **Last Amended**: 2026-11-12
