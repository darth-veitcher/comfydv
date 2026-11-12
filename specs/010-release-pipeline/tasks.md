---
description: "Task list for the release pipeline"
---

# Tasks: Release Pipeline and Distribution

**Input**: Design documents from `specs/010-release-pipeline/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required. The spec has acceptance scenarios, so each user story is a set of TDD pairs.
A `-T` task writes a failing test and is committed alone. Its `-I` partner makes the test pass.

**Rule ids**: C1 to C8 are the rules in `contracts/ci-gate.md` (the quality gate). W1 to W10, P1 to
P8, G1 and G2 are the rules in `contracts/release-workflow.md` (the release workflow, `pyproject.toml`
and the repository state).

**Deferred tasks** (`[-]`): they need the live pipeline after a merge, or a maintainer action
outside this branch. Each one says why.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: The user story of the task (US1 to US4)

---

## Phase 1: Setup

**Purpose**: Get BEACON's release template and the test file skeleton.

- [x] T001 Run `beacon integration add release` and record the files that it writes, in `specs/010-release-pipeline/research.md` (R2).
- [x] T002 Create `tests/test_release_pipeline.py` with helpers that load `.github/workflows/*.yml` and `pyproject.toml`, and no tests yet.

---

## Phase 2: Foundational (blocks US2 and US3)

**Purpose**: A static version and the PSR configuration. Both release paths need them.

- [x] T003-T Write FAILING tests for P1 (the name is `comfydv`) and P2 (a static `version`, not dynamic) in `tests/test_release_pipeline.py`.
- [x] T003-I Replace `hatch-vcs` with `version = "0.1.0"` in `pyproject.toml`, so that T003-T passes.
- [x] T004-T Write FAILING tests for P4 to P8 (the PSR version source, zero-version rules, commit tags, `develop` pre-release token and changelog mode) in `tests/test_release_pipeline.py`.
- [x] T004-I Add `[tool.semantic_release]` to `pyproject.toml` from the T001 template, changed as research R4, R5 and R12 say, so that T004-T passes.
- [x] T005-T Write a FAILING test that `torch` comes from the PyTorch CPU index and that `torchvision` is absent, in `tests/test_release_pipeline.py`.
- [x] T005-I Add the CPU index for `torch` to `[tool.uv.sources]`, remove `torchvision` from the dev group in `pyproject.toml`, and run `uv lock`.

**Checkpoint**: `uv build` makes `comfydv-0.1.0` packages, and the full test suite passes.

---

## Phase 3: User Story 1 — Block a merge that fails the quality gates (P1) 🎯 MVP

**Goal**: Each pull request to `develop` or `main` runs the `quality-gate` check.

**Independent Test**: A pull request with a failing test fails `quality-gate`. Scenarios: `features/us1_quality_gate.feature`.

- [x] T010-T [US1] Write FAILING tests for C1 to C8 in `tests/test_release_pipeline.py`, one test for each rule.
- [x] T010-I [US1] Write `.github/workflows/ci.yml` so that T010-T passes.
- [x] T011 [US1] Add the `quality-gate` check and the CI tiers to the Commands section of `AGENTS.md`.
- [-] T012 [US1] Do quickstart scenario 1 on a test pull request. _Deferred — needs `ci.yml` on GitHub, after this branch merges._
- [-] T013 [US1] Add `quality-gate` as a required status check in the `develop` and `main` rulesets. _Deferred — maintainer action in the GitHub settings, after the check has run once._

**Checkpoint**: US1 works alone. It protects the branches with no release pipeline.

---

## Phase 4: User Story 2 — Publish a stable release from `main` (P1)

**Goal**: A merge to `main` makes a tag, a changelog entry and a GitHub Release, and publishes to PyPI and the Comfy Registry.

**Independent Test**: Scenarios in `features/us2_stable_release.feature`.

- [x] T020-T [US2] Write FAILING tests for W1 to W4, W6 and W8 in `tests/test_release_pipeline.py`.
- [x] T020-I [US2] Change the T001 `release.yml` into `.github/workflows/release.yml` (the `pypi` environment for both branches, `skip-existing: true` and SHA-pinned actions), so that T020-T passes.
- [x] T021-T [US2] Write FAILING tests for W7 (the Registry step), W10 (the Registry check) and P3 (`PublisherId`) in `tests/test_release_pipeline.py`.
- [ ] T021-I [US2] Add the Comfy Registry publish step and its check to `.github/workflows/release.yml`, and add `[tool.comfy]` to `pyproject.toml`, so that T021-T passes.
- [ ] T022-T [US2] Write FAILING tests for W9 (merge `main` into `develop`) and G2 (`.comfyignore`) in `tests/test_release_pipeline.py`.
- [ ] T022-I [US2] Keep the sync step in `.github/workflows/release.yml` and add `.comfyignore`, so that T022-T passes.
- [ ] T023-T [US2] Write a FAILING test that `CHANGELOG.md` has the PSR insertion flag above the hand-written entries, in `tests/test_release_pipeline.py`.
- [ ] T023-I [US2] Add the insertion flag to `CHANGELOG.md`, and rename the `[Unreleased]` heading as research R12 says, so that T023-T passes.
- [ ] T024 [US2] Write the stable-release install steps in the Install section of `README.md`.
- [ ] T025 [US2] Write `PUBLISHING.md` from the T001 template, with the one-time setup and the ruleset bypass of research R7.
- [x] T026 [US2] Confirm that the tag `v0.1.0` exists for G1. It is on commit `4f69405` (2026-07-04), so no tag push is necessary.
- [-] T027 [US2] Add GitHub Actions as a push-only bypass actor in the `main` and `develop` rulesets. _Deferred — maintainer action in the GitHub settings (research R7)._
- [-] T028 [US2] Do quickstart scenarios 4 and 5. _Deferred — needs a release pull request to `main`._

**Checkpoint**: The contract tests for US2 pass. The live release waits on T027 and T028.

---

## Phase 5: User Story 3 — Test a development build before users get it (P2)

**Goal**: A merge to `develop` publishes a PyPI pre-release, and a normal install ignores it.

**Independent Test**: Scenarios in `features/us3_dev_prerelease.feature`.

- [ ] T030-T [US3] Write a FAILING test for W5 (`--no-commit` on `develop` only) in `tests/test_release_pipeline.py`.
- [ ] T030-I [US3] Make PSR run with `--no-commit` on `develop` only in `.github/workflows/release.yml`, so that T030-T passes.
- [ ] T031 [US3] Write the pre-release install steps (`pip install --pre comfydv`) in the Install section of `README.md`.
- [-] T032 [US3] Do quickstart scenario 3. _Deferred — needs a merge to `develop` with the pipeline in place._

**Checkpoint**: US3 works with US2 or without it, because `develop` runs the same workflow.

---

## Phase 6: User Story 4 — Map ComfyUI Manager "nightly" to `develop` (P3)

**Goal**: Evidence for the default-branch decision.

**Independent Test**: Scenarios in `features/us4_manager_nightly.feature`.

- [-] T040 [US4] Do quickstart scenario 6, and record the branch and commit that "nightly" clones. _Deferred — needs the first Registry release and a real ComfyUI._
- [-] T041 [US4] Write an ADR in `project-management/ADRs/` with the evidence from T040 and the decision. _Deferred — depends on T040._
- [-] T042 [US4] Point the ComfyUI Manager entry in `comfy-manager-entry.json` at the Comfy Registry, before any default-branch change (FR-028). _Deferred — depends on T041._

---

## Phase 7: Polish

- [ ] T050 Write the release commands in the Commands section of `AGENTS.md`, and remove the text "Until then, no package publishes".
- [ ] T051 Add the release pipeline and its channels to the Technical notes of `README.md`.
- [ ] T052 Run `beacon docs check`, then the two review passes of the `beacon-docs` skill, on `README.md`, `AGENTS.md` and `PUBLISHING.md`.
- [ ] T053 Run the quality gates: `uv run ruff check`, `uv run ruff format --check`, `uv run ty check`, `uv run pytest` and `beacon doctor --strict`.

---

## Dependencies

- Phase 1 → Phase 2 → US1, US2 and US3. US1 needs only Phase 1, so it can start first.
- US2 and US3 both change `.github/workflows/release.yml`, so do them in sequence: US2, then US3.
- US4 depends on a live US2 release.
- Polish comes last.

## Parallel opportunities

- T003 to T005 change different sections of `pyproject.toml`, so do them in sequence.
- After Phase 2, US1 (`ci.yml`) and US2 (`release.yml`) can run in parallel.
- T024, T025 and T031 change documentation only, and can run in parallel with the test pairs.

## Implementation strategy

1. **MVP**: Phase 1, Phase 2 and US1. Merge it, and the branches have a gate.
2. Then US2 and US3, with the documentation tasks.
3. Then the maintainer does T027, and the first release runs (T028, T032).
4. US4 follows the first Registry release.
