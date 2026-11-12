# Implementation Plan: Release Pipeline and Distribution

**Branch**: `claude/cool-rubin-qydf3s` | **Date**: 2026-11-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/010-release-pipeline/spec.md`

## Summary

comfydv gets a CI quality gate and an automatic release pipeline on GitHub Actions. Each pull
request to `develop` or `main` runs the `quality-gate` check. python-semantic-release (PSR)
calculates each version from the Conventional Commits.

- A merge to `develop` publishes a PyPI pre-release (`X.Y.Z.devN`).
- A merge to `main` makes a release commit, a tag and a GitHub Release. It publishes to PyPI and to
  the Comfy Registry.

The base is BEACON's `gitflow` release integration, changed as ADR-017 records.

## Technical Context

**Language/Version**: Python 3.11 to 3.13 (`requires-python = ">=3.11"`). Workflows in GitHub Actions YAML.

**Primary Dependencies**: `python-semantic-release==9.21.2` with `gitpython<3.1.60` (BEACON pin),
`pypa/gh-action-pypi-publish`, `Comfy-Org/publish-node-action` (pinned to a SHA), `astral-sh/setup-uv`.

**Storage**: Not applicable. The state is git tags, `pyproject.toml`, `CHANGELOG.md` and the indexes.

**Testing**: pytest. A contract test (`tests/test_release_pipeline.py`) parses the workflows and
`pyproject.toml` with `pyyaml` and `tomllib`. The quickstart scenarios validate the live pipeline.

**Target Platform**: GitHub-hosted `ubuntu-latest` runners.

**Project Type**: Python library and ComfyUI node pack. This feature adds build and release infrastructure.

**Performance Goals**: A release finishes in less than 15 minutes (SC-002, SC-003). The gate must
install fast, so `torch` comes from the CPU index (research R11).

**Constraints**:
- No PyPI token: Trusted Publishing only (FR-021).
- A fork gets no secrets (FR-003).
- The rulesets on `main` and `develop` need a bypass for the release pushes (research R7).

**Scale/Scope**: Two workflows, one contract test file, changes to `pyproject.toml`, `CHANGELOG.md`,
`README.md`, `AGENTS.md` and a new `PUBLISHING.md`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Check | Result |
|---|---|---|
| I. ComfyUI Contract First | No node changes. `[tool.comfy]` adds Registry metadata only. | Pass |
| II. Sandbox user code | No templates or user code. | Pass |
| III. Test-First | The contract test is written first, for each rule in `contracts/`. It runs without ComfyUI. | Pass |
| IV. Graceful degradation | No import changes. | Pass |
| V. Simplicity | Start from BEACON's template, and change only two points. Use one summary check, not a check for each Python version. | Pass |
| VI. Fixed output positions | No node outputs change. | Pass |
| VII. Documentation | Users can see the new install channels. `README.md` (Install, Technical notes, Develop), `AGENTS.md` (Commands) and a new `PUBLISHING.md` change in the same pull request. | Pass |

**Post-design re-check (after Phase 1):** still Pass. The design adds no node code. The bypass in
research R7 is a repository setting, not code, and ADR-017 records it.

## Project Structure

### Documentation (this feature)

```text
specs/010-release-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1 to R14
├── data-model.md        # Phase 1: Release, Pre-release, Channel, Quality gate, version state
├── quickstart.md        # Phase 1: live validation scenarios
├── contracts/
│   ├── ci-gate.md          # Rules C1 to C8
│   └── release-workflow.md # Rules W1 to W10, P1 to P8, G1 and G2
├── features/            # Gherkin contracts for each user story
├── checklists/
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
.github/workflows/
├── ci.yml               # NEW: the quality gate (contracts/ci-gate.md)
├── release.yml          # NEW: PSR, PyPI, Comfy Registry (contracts/release-workflow.md)
└── docs.yml             # unchanged
pyproject.toml           # static version, [tool.comfy], [tool.semantic_release], CPU torch source
.comfyignore             # NEW: files to keep out of the Registry archive
CHANGELOG.md             # PSR insertion flag; hand-written section renamed
PUBLISHING.md            # NEW: maintainer guide (FR-031)
README.md                # Install: stable and pre-release; Technical notes; Develop
AGENTS.md                # Commands: CI gate and release
tests/
└── test_release_pipeline.py   # NEW: contract tests
```

**Structure Decision**: The feature adds two workflow files, one test file and three small files
at the repository root. It changes no `src/` code.

## Implementation order

1. Write the contract tests (`tests/test_release_pipeline.py`) and confirm that they fail.
2. Change `pyproject.toml`: static version `0.1.0`, `[tool.comfy]`, `[tool.semantic_release]`, CPU `torch`, no `torchvision`.
3. Add `.github/workflows/ci.yml`. Open a pull request, and confirm that `quality-gate` runs.
4. Run `beacon integration add release`, then change the generated `release.yml`. Make the PyPI and Registry changes of ADR-017.
5. Add `.comfyignore`, and prepare `CHANGELOG.md` (research R12).
6. Write `PUBLISHING.md`, and change `README.md` and `AGENTS.md`.
7. After the merge: tag `v0.1.0` on `abe055e`, then do the quickstart scenarios.

## Complexity Tracking

No violations. This section is empty.
