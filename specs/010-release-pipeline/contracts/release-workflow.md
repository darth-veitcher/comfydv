# Contract: release workflow (`.github/workflows/release.yml`) and its configuration

A contract test (`tests/test_release_pipeline.py`) parses the workflow file and `pyproject.toml`,
and checks each rule.

## Workflow

| # | Rule | Requirement |
|---|---|---|
| W1 | The workflow runs on `push` to `main` and to `develop`, and on `workflow_dispatch`. | FR-012, FR-018 |
| W2 | `concurrency` groups runs by branch, with `cancel-in-progress: false`. | FR-022 |
| W3 | The release job uses the GitHub environment `pypi`. | FR-021 |
| W4 | `permissions` is `contents: write` and `id-token: write`, and nothing more. | FR-021 |
| W5 | PSR runs with `--no-commit` on `develop` only. | FR-020 |
| W6 | The PyPI publish step uses `pypa/gh-action-pypi-publish` with `skip-existing: true`, and no `password` input. | FR-021, FR-023 |
| W7 | The Comfy Registry step runs only on `main`, only when PSR released, and uses `secrets.REGISTRY_ACCESS_TOKEN`. | FR-016, FR-019 |
| W8 | Each third-party action outside `actions/*` and `pypa/*` is pinned to a commit SHA. | R8 |
| W9 | After a stable release, a step merges `main` into `develop`. | FR-017 |
| W10 | After the Registry step, a step reads `https://api.comfy.org/nodes/comfydv/versions` and fails if the new version is missing. | SC-002, R13 |

## `pyproject.toml`

| # | Rule | Requirement |
|---|---|---|
| P1 | `[project] name` is `comfydv`. | FR-033 |
| P2 | `[project] version` is a static string, and `dynamic` does not contain `version`. | FR-005 |
| P3 | `[tool.comfy] PublisherId` is `darth-veitcher`. | FR-032 |
| P4 | `[tool.semantic_release] version_toml` is `["pyproject.toml:project.version"]`. | FR-006 |
| P5 | `major_on_zero = false` and `allow_zero_version = true`. | FR-009 |
| P6 | `minor_tags = ["feat"]` and `patch_tags = ["fix", "perf"]`. | FR-007, FR-008, FR-010 |
| P7 | The `develop` branch config has `prerelease = true` and `prerelease_token = "dev"`. | FR-011 |
| P8 | `changelog.mode = "update"`. | FR-013, FR-026 |

## Repository state

| # | Rule | Requirement |
|---|---|---|
| G1 | The tag `v0.1.0` exists on commit `abe055e`. The quickstart checks it, not a test, because a CI checkout has no tags. | FR-025 |
| G2 | `.comfyignore` excludes `tests/`, `specs/`, `project-management/` and `docs/`. | R8 |
