# Research: Release Pipeline and Distribution

Each decision has the form: decision, rationale, alternatives. The facts come from the repository
and from the sources named in each item, on 2026-11-12.

## R1. CI service

- **Decision**: GitHub Actions.
- **Rationale**: The repository is on GitHub, and `.github/workflows/docs.yml` already uses
  Actions. PyPI Trusted Publishing and the Comfy Registry action both support Actions.
- **Alternatives**: None evaluated. A second CI service adds an account and a secret for no gain.

## R2. Release tool

- **Decision**: python-semantic-release (PSR), from BEACON's `gitflow` release integration
  (`beacon integration add release`).
- **Rationale**: PSR reads Conventional Commits, which the `commit-msg` hook already enforces. It
  calculates the version, writes `pyproject.toml` and `CHANGELOG.md`, tags and creates the GitHub
  Release. BEACON ships and maintains a tested workflow and config for it.
- **Pin**: BEACON's template pins `python-semantic-release==9.21.2` and `gitpython<3.1.60`. GitPython
  3.1.60 removed an attribute that PSR uses. Keep that pin, and its comment.
- **Alternatives**:
  - release-please: it works through release PRs, which duplicates the `develop → main` release PR.
  - Manual tags: they fail SC-005 (no manual edits to the version or the changelog).

## R3. Version source

- **Decision**: replace `hatch-vcs` with a static `version` in `[project]` in `pyproject.toml`.
- **Rationale**: The Comfy Registry reads the literal `version` field, and PSR writes that field
  (`version_toml`). A version that only git tags hold is not visible to the Registry action.
- **Alternatives**: Keep `hatch-vcs` and write a version file for the Registry. That gives two
  sources of the version, which is not DRY.

## R4. Pre-release format

- **Decision**: PSR `prerelease_token = "dev"` on `develop`.
- **Rationale**: PSR makes `0.3.0-dev.1`. PEP 440 normalises it to `0.3.0.dev1`, which is a
  pre-release (verified: `packaging.version.Version("0.3.0-dev.1")` gives `0.3.0.dev1`, and
  `is_prerelease` is `True`). pip and uv skip it unless the user asks for it.
- **Alternatives**: `rc` pre-releases. They mean "release candidate", which is wrong for each
  merge to `develop`.

## R5. Pre-release index

- **Decision**: PyPI, not TestPyPI. This is a change from BEACON's template, which uses TestPyPI.
- **Rationale**: TestPyPI does not host the dependencies (pydantic-ai, fastmcp, monty). An install
  from it needs a second index, and that is open to dependency confusion. PyPI pre-releases are
  hidden from a normal install (R4).
- **Consequence**: one Trusted Publisher and one GitHub environment, `pypi`, for both branches.
  The maintainer created both on 2026-11-12.

## R6. Pre-release commits

- **Decision**: on `develop`, run PSR with `--no-commit`. PSR still tags and publishes.
- **Rationale**: FR-020 says that a pre-release does not change `develop`. If `develop` held
  pre-release versions, each `develop → main` PR would conflict on `pyproject.toml` and
  `CHANGELOG.md`. The git tags (`v0.3.0-dev.N`) let PSR count the next `N`.

## R7. Protected branches and the release commit

- **Problem**: PSR pushes a release commit and a tag to `main`. After a release, the workflow
  merges `main` into `develop` (FR-017). The maintainer's rulesets on `main` and `develop` require
  pull requests, so they block both pushes from the workflow.
- **Decision**: add the GitHub Actions integration as a bypass actor in both rulesets, for pushes
  only. Only `release.yml` has `contents: write`. `ci.yml` has `contents: read`.
- **Rationale**: It is the smallest change that lets the pipeline write the release commit, and the
  maintainer can see it in the ruleset settings.
- **Alternatives**:
  - A GitHub App or a deploy key with bypass: more secure, but more setup and one more secret.
    Use it if a second workflow ever needs `contents: write`.
  - `--no-commit` on `main` too: then `pyproject.toml` and `CHANGELOG.md` in the repository never
    get the release version. That fails FR-005 and FR-013.
- **Maintainer action**: add the bypass (see `quickstart.md`, step 0).

## R8. Comfy Registry publish

- **Decision**: run `Comfy-Org/publish-node-action` as a step in the same release job, after PSR
  releases on `main`. Pass `secrets.REGISTRY_ACCESS_TOKEN`.
- **Rationale**: The Registry docs trigger the action on a push to `main` that changes
  `pyproject.toml`. But PSR pushes with `GITHUB_TOKEN`, and a push with `GITHUB_TOKEN` does not
  start other workflows. So a separate workflow would never run.
- **Pin**: the docs give only `@main`. Pin the action to a commit SHA, because a third-party action
  runs with the Registry key.
- **Registry fields**: `[tool.comfy] PublisherId = "darth-veitcher"`, `DisplayName = "Comfy DV"`.
  The project name stays `comfydv`, because the Registry node ID is `comfydv`.
- **Archive contents**: add a `.comfyignore` that excludes `tests/`, `specs/`, `project-management/`,
  `docs/`, `docker/` and the dev files. The Registry archive then has only what ComfyUI loads.

## R9. Idempotent re-runs

- **Decision**: `pypa/gh-action-pypi-publish` with `skip-existing: true`. PSR does not release a
  version whose tag exists.
- **Rationale**: FR-023. A re-run after a Registry failure skips PyPI and tries the Registry again.

## R10. The quality gate

- **Decision**: a workflow `ci.yml` on `pull_request` to `develop` and `main`. It has a matrix job
  for Python 3.11, 3.12 and 3.13, and one summary job `quality-gate` that needs the matrix.
- **Rationale**:
  - A ruleset names one required check. The summary job gives one stable name, whatever the matrix.
  - ComfyUI installs use Python 3.11 to 3.13, and `requires-python` is `>=3.11`.
  - The `pull_request` event gives a fork no secrets (FR-003). The gate MUST NOT use
    `pull_request_target`.
  - `uv sync --frozen` installs the versions in `uv.lock` (FR-004).
- **Steps**: `ruff check`, `ruff format --check`, `ty check`, and
  `pytest -m "not integration and not system"`.

## R11. Test dependencies in CI

- **Problem**: the dev group installs `torch` with CUDA: 1.7 GB of `torch` and 4.3 GB of `nvidia-*`
  packages (measured in `.venv`). Only three tests in `tests/test_ollama.py` use `torch`, to make
  small tensors. No code or test uses `torchvision`.
- **Decision**: take `torch` from the PyTorch CPU index with `[tool.uv.sources]`, on Linux and
  Windows. Remove `torchvision` from the dev group.
- **Rationale**: The CPU wheel is about 200 MB. It makes the gate fast enough for SC-002 and SC-003.
  The tests check the tensor path, not CUDA.
- **Alternatives**: remove `torch` and test only NumPy arrays. That loses the test of the
  `.detach()` path in `_encode_image_tensor`.

## R12. Changelog bootstrap

- **Decision**:
  - Tag `v0.1.0` on `abe055e`. This is the last `main` commit before the BEACON bootstrap
    (2025-11-05).
  - Use PSR `changelog.mode = "update"`, with the insertion flag above the hand-written entries.
  - Rename the hand-written `## [Unreleased]` heading to "Notes for 0.2.0 (written by hand)".
- **Rationale**:
  - PSR counts the commits after `v0.1.0`. Those commits are the ones that the `[Unreleased]`
    entries describe, so the first release contains them (FR-026).
  - `update` mode keeps the hand-written history, and the rename happens once, in the bootstrap.
- **Fact**: the `[0.1.0]` entry has the date 2026-06-01, but no commit has that date. The entry was
  written later. The tag uses the real commit.

## R13. Verification of "latest"

- **Decision**: after the Registry step, the release job reads
  `https://api.comfy.org/nodes/comfydv/versions` and fails if the new version is not there.
- **Rationale**: SC-002 needs evidence, not only an exit code from the action.

## R14. ComfyUI Manager "nightly"

- **Decision**: a manual check, after the first Registry release. Record the result in an ADR.
- **Rationale**: The Manager docs say only that "nightly" is "the latest version updated by authors
  to github". The check needs a real ComfyUI and Manager, which CI does not have.
- **Procedure**: `quickstart.md`, scenario 6.
