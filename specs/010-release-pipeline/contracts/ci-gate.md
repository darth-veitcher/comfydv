# Contract: CI quality gate (`.github/workflows/ci.yml`)

This contract is the interface between the workflow and the branch rulesets. A contract test
(`tests/test_release_pipeline.py`) parses the workflow file and checks each rule.

| # | Rule | Requirement |
|---|---|---|
| C1 | The workflow runs on `pull_request` with `branches: [develop, main]`. | FR-001 |
| C2 | The workflow MUST NOT use `pull_request_target`. | FR-003 |
| C3 | The top-level `permissions` is `contents: read`, and no job widens it. | FR-003 |
| C4 | No step refers to `secrets.`. | FR-003 |
| C5 | A matrix job runs on Python 3.11, 3.12 and 3.13. | R10 |
| C6 | The install step runs `uv sync --frozen`. | FR-004 |
| C7 | The steps run `ruff check`, `ruff format --check`, `ty check` and `pytest -m "not integration and not system"`. | FR-001 |
| C8 | A job named `quality-gate` needs the matrix job and fails if the matrix fails. | FR-002 |

The rulesets on `develop` and `main` name `quality-gate` as a required status check. The check
name is the stable interface: change it only together with the rulesets.
