# Quickstart: validate the release pipeline

Do these scenarios in order after the implementation merges to `develop`. Each scenario names the
requirement or the success criterion that it proves.

## 0. Prerequisites (maintainer, one time)

- Done on 2026-11-12: the PyPI Trusted Publisher, the `pypi` environment, the Comfy Registry
  publisher `darth-veitcher` with node `comfydv`, the `REGISTRY_ACCESS_TOKEN` secret and the rulesets.
- Still to do:
  1. In each ruleset (`main` and `develop`), add **GitHub Actions** as a bypass actor for pushes (research R7).
  2. In each ruleset, add `quality-gate` as a required status check (contract `ci-gate.md`).

## 1. The gate blocks a failing pull request (US1, SC-001)

1. Open a pull request to `develop` that adds `assert False` to a unit test.
2. Wait for the `quality-gate` check.
3. Expected result: the check fails, and GitHub does not let you merge.
4. Remove the change. Expected result: the check passes.

## 2. The contract tests pass locally

```bash
uv run pytest tests/test_release_pipeline.py -v
```

Expected result: each rule in `contracts/ci-gate.md` and `contracts/release-workflow.md` passes.

## 3. A merge to `develop` publishes a pre-release (US3, SC-003, SC-004)

1. Merge a pull request with a `feat:` commit to `develop`.
2. Wait for the `Release` workflow. Expected result: it finishes in less than 15 minutes.
3. Look at https://pypi.org/project/comfydv/#history. Expected result: a version like `0.2.0.dev1`.
4. In a clean environment, run `pip install comfydv`. Expected result: pip installs the last stable version.
5. Run `pip install --pre comfydv`. Expected result: pip installs the pre-release.
6. Run `curl -s https://api.comfy.org/nodes/comfydv/versions`. Expected result: no pre-release version.

## 4. A release from `main` publishes everywhere (US2, SC-002, SC-005, SC-006)

1. Run `/git:release` to open the pull request from `develop` to `main`. Merge it.
2. Wait for the `Release` workflow. Expected result: it finishes in less than 15 minutes.
3. Expected result: all of these exist for the new version:
   - the tag `vX.Y.Z` and a commit `chore(release): X.Y.Z` on `main`
   - a GitHub Release with the changelog entry and two files (wheel and sdist)
   - the version on https://pypi.org/project/comfydv/
   - the version in `curl -s https://api.comfy.org/nodes/comfydv/versions`
4. Expected result: `develop` contains the release commit.
5. Expected result: you edited no version and no changelog by hand.

## 5. A re-run publishes no duplicate (SC-007)

1. In GitHub Actions, run the last `Release` run again.
2. Expected result: it succeeds, and PyPI and the Registry show no second copy of the version.

## 6. Find the branch that ComfyUI Manager "nightly" clones (US4, SC-008)

1. In a test ComfyUI, set `security_level = weak` in the ComfyUI Manager `config.ini`.
2. In ComfyUI Manager, install comfydv and select the version **nightly**.
3. In `custom_nodes/comfydv`, run `git rev-parse --abbrev-ref HEAD` and `git rev-parse HEAD`.
4. Record the branch, the commit and the date in a new ADR.
5. Set `security_level` back to its earlier value.
