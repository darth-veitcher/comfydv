# Feature Specification: Release Pipeline and Distribution

**Feature Branch**: `claude/cool-rubin-qydf3s`

**Created**: 2026-11-12

**Status**: Draft

**Input**: User description:

```text
Release pipeline and distribution: CI quality gate on PRs to develop and main; static version bumped by python-semantic-release from Conventional Commits; develop publishes PyPI pre-releases (X.Y.Z.devN); main tags, creates a GitHub Release with changelog, publishes to PyPI and the Comfy Registry; verify ComfyUI-Manager nightly maps to the default branch before switching the default branch to develop
```

**Epic**: `release-pipeline` (`project-management/Roadmap/epics/release-pipeline.md`)

## User Scenarios & Testing *(mandatory)*

The three actors are:

- **The maintainer**, who merges pull requests and approves releases.
- **A contributor**, who opens a pull request.
- **A ComfyUI user**, who installs comfydv with ComfyUI Manager or with pip.

### User Story 1 - Block a merge that fails the quality gates (Priority: P1)

A contributor opens a pull request to `develop` or to `main`. An automatic check runs the
project's quality gates. A failure blocks the merge, so broken code cannot reach a release.

**Why this priority**: The other stories publish what is on `develop` and `main`. Without this
gate, a release can contain a lint error, a type error or a failing test.

**Independent Test**: Open a pull request with a failing test. The check fails and the merge is
blocked. Fix the test. The check passes and the merge is allowed.

**Acceptance Scenarios**:

1. **Given** a pull request to `develop` with a failing unit test, **When** the check runs, **Then** the check reports a failure.
2. **Given** a pull request to `main` with a lint error, **When** the check runs, **Then** the check reports a failure.
3. **Given** a pull request that passes all the gates, **When** the check runs, **Then** the check reports success.
4. **Given** a pull request from a fork, **When** the check runs, **Then** the check runs without access to the publishing credentials.

---

### User Story 2 - Publish a stable release from `main` (Priority: P1)

The maintainer merges a release pull request from `develop` to `main`. The pipeline calculates
the next version from the commit messages. It tags the commit, writes the changelog and creates a
GitHub Release. It publishes the package to PyPI and to the Comfy Registry.

**Why this priority**: Today each merge to `main` goes to users with no version and no changelog.
A user cannot see what changed, and cannot go back to an earlier version.

**Independent Test**: Merge a release pull request that contains one `feat:` commit. A new minor
version appears as a git tag, as a GitHub Release, on PyPI and on the Comfy Registry.

**Acceptance Scenarios**:

1. **Given** a merge to `main` with a `feat:` commit since the last release, **When** the pipeline runs, **Then** it publishes a new minor version.
2. **Given** a merge to `main` with only `fix:` commits since the last release, **When** the pipeline runs, **Then** it publishes a new patch version.
3. **Given** a merge to `main` with a `BREAKING CHANGE` footer while the version is 0.x, **When** the pipeline runs, **Then** it publishes a new minor version.
4. **Given** a merge to `main` with only `docs:` and `chore:` commits, **When** the pipeline runs, **Then** it publishes no new version.
5. **Given** a new stable release, **When** a user runs `pip install comfydv`, **Then** pip installs that release.
6. **Given** a new stable release, **When** a user opens ComfyUI Manager, **Then** the Manager shows that release as "latest".

---

### User Story 3 - Test a development build before users get it (Priority: P2)

The maintainer merges a pull request to `develop`. The pipeline publishes a pre-release to PyPI.
The maintainer installs that pre-release on purpose and tests it. Users who install normally do
not get it.

**Why this priority**: The maintainer wants to test a change in a real ComfyUI before it reaches
users. Story 1 and Story 2 deliver value without this story, so it is P2.

**Independent Test**: Merge a `feat:` commit to `develop`. A version like `0.3.0.dev1` appears on
PyPI. `pip install comfydv` still installs the last stable release.

**Acceptance Scenarios**:

1. **Given** a merge to `develop` with a `feat:` commit, **When** the pipeline runs, **Then** it publishes a pre-release version to PyPI.
2. **Given** a pre-release on PyPI, **When** a user runs `pip install comfydv`, **Then** pip installs the last stable release.
3. **Given** a pre-release on PyPI, **When** the maintainer runs `pip install --pre comfydv`, **Then** pip installs the pre-release.
4. **Given** a merge to `develop`, **When** the pipeline runs, **Then** it publishes nothing to the Comfy Registry.

---

### User Story 4 - Map ComfyUI Manager "nightly" to `develop` (Priority: P3)

The maintainer finds out which branch the ComfyUI Manager "nightly" version installs. If it is
the default branch, the maintainer can make `develop` the default branch. Then "nightly" gives
the development build, and "latest" gives the stable release.

**Why this priority**: It is a convenience for testers. The ComfyUI Manager docs do not say which
branch "nightly" uses, so the change needs evidence first.

**Independent Test**: In a test ComfyUI, install comfydv "nightly" with ComfyUI Manager. Record the
branch and the commit that it cloned.

**Acceptance Scenarios**:

1. **Given** comfydv is on the Comfy Registry, **When** the maintainer installs "nightly", **Then** the record names the branch and commit that the Manager cloned.
2. **Given** the record shows the default branch, **When** the maintainer decides, **Then** the decision and its evidence are in an ADR.
3. **Given** `develop` becomes the default branch, **When** a user installs from the legacy git-clone entry, **Then** that entry no longer clones `develop`.

---

### Edge Cases

- A merge to `main` has no commit that changes the version. The pipeline publishes nothing and does not fail.
- PyPI accepts a release, but the Comfy Registry rejects it. The pipeline fails, and a re-run publishes only to the Registry.
- A re-run of the pipeline finds that the version is already on PyPI. The pipeline does not publish it again and does not fail.
- A publishing credential is missing or wrong. The pipeline fails, and its log names the credential.
- `develop` and `main` have different versions after a stable release. The pipeline brings `develop` up to date with `main`.
- Two merges to the same branch occur close together. The second pipeline run waits for the first to finish.

## Requirements *(mandatory)*

### Functional Requirements

**Quality gate**

- **FR-001**: Each pull request to `develop` or to `main` MUST run the lint check, the format check, the type check and the unit tests.
- **FR-002**: A pull request MUST NOT merge while a gate in FR-001 fails.
- **FR-003**: The gate MUST NOT give a pull request from a fork access to the publishing credentials.
- **FR-004**: The gate MUST use the tool versions that `uv.lock` pins.

**Versions**

- **FR-005**: The package version MUST be a fixed value in `pyproject.toml`, because the Comfy Registry reads only that value.
- **FR-006**: The pipeline MUST calculate each new version from the Conventional Commit messages since the last release.
- **FR-007**: A `feat:` commit MUST cause a minor version increase.
- **FR-008**: A `fix:` or `perf:` commit MUST cause a patch version increase.
- **FR-009**: While the major version is 0, a breaking change MUST cause a minor version increase, not a major one.
- **FR-010**: A release with only `docs:`, `chore:`, `ci:`, `test:`, `style:` or `refactor:` commits MUST NOT publish a version.
- **FR-011**: A pre-release version MUST use the PEP 440 form `X.Y.Z.devN`.

**Stable release from `main`**

- **FR-012**: A merge to `main` that changes the version MUST create a git tag `vX.Y.Z`.
- **FR-013**: A stable release MUST add an entry to `CHANGELOG.md`, with the changes grouped by type.
- **FR-014**: A stable release MUST create a GitHub Release with the changelog entry and the built packages.
- **FR-015**: A stable release MUST publish the package to PyPI.
- **FR-016**: A stable release MUST publish the package to the Comfy Registry.
- **FR-017**: After a stable release, the pipeline MUST merge `main` into `develop`.

**Development release from `develop`**

- **FR-018**: A merge to `develop` that changes the version MUST publish a pre-release to PyPI.
- **FR-019**: A pre-release MUST NOT go to the Comfy Registry.
- **FR-020**: A pre-release MUST NOT change the version or the changelog on `develop`.

**Safety and repeatability**

- **FR-021**: Publishing to PyPI MUST use Trusted Publishing, so the repository stores no PyPI token.
- **FR-022**: A pipeline run MUST NOT start on a branch while another run on that branch is active.
- **FR-023**: A re-run of a failed pipeline MUST NOT publish a version that is already on an index.
- **FR-024**: A failure MUST name the step that failed, and the credential when a credential is the cause.

**Bootstrap**

- **FR-032**: `pyproject.toml` MUST set `[tool.comfy] PublisherId` to `darth-veitcher`.
- **FR-033**: The project name MUST stay `comfydv`, because the Comfy Registry node ID is `comfydv` and cannot change.
- **FR-034**: Before the first stable release, the Comfy Registry node `comfydv` MUST belong to the publisher `darth-veitcher`.

- **FR-025**: Before the first pipeline run, `main` MUST have the tag `v0.1.0`, so the first release counts commits from that point.
- **FR-026**: The existing `[Unreleased]` changelog entries MUST appear in the first release.

**ComfyUI Manager channels**

- **FR-027**: Before the default branch changes, an ADR MUST record which branch ComfyUI Manager "nightly" clones, with the evidence.
- **FR-028**: Before the default branch becomes `develop`, the ComfyUI Manager entry MUST point to the Comfy Registry, not to a git clone.

**Documentation**

- **FR-029**: `README.md` MUST tell users how to install a stable release and how to install a pre-release.
- **FR-030**: `AGENTS.md` MUST give the release commands and the CI gate.
- **FR-031**: A maintainer guide MUST list the one-time setup steps for PyPI, the Comfy Registry and branch protection.

### Key Entities

- **Release**: one version of comfydv. It has a version number, a git tag, a changelog entry, a GitHub Release and its published packages.
- **Pre-release**: a development version from `develop`. It has a version number and a PyPI package, and no changelog entry.
- **Channel**: a place that a user installs from: PyPI stable, PyPI pre-release, Comfy Registry "latest", or ComfyUI Manager "nightly".
- **Quality gate**: the set of checks that must pass before a merge.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of pull requests to `develop` and `main` run the quality gate. A test pull request with a failing test is blocked.
- **SC-002**: A merge to `main` with a releasable commit gives a tag, a GitHub Release, a PyPI release and a Comfy Registry release. All four exist within 15 minutes.
- **SC-003**: A merge to `develop` with a releasable commit gives a PyPI pre-release within 15 minutes.
- **SC-004**: After a pre-release, `pip install comfydv` in a clean environment installs the last stable version in 100% of attempts.
- **SC-005**: The maintainer releases with 0 manual edits to the version or the changelog.
- **SC-006**: The repository contains 0 PyPI tokens. The only publishing secret is the Comfy Registry key.
- **SC-007**: A re-run of a completed release publishes 0 duplicate versions.
- **SC-008**: The "nightly" branch question has an answer with evidence, recorded in 1 ADR.

## Assumptions

- The maintainer did the one-time setup on 2026-11-12. It includes the PyPI Trusted Publisher, the Comfy Registry publisher and key, the `pypi` environment and the branch rulesets.
- The rulesets get the CI check as a required status check when the plan names it.
- The Comfy Registry publisher ID is `darth-veitcher` (created 2026-11-12). It cannot change.
- The Comfy Registry already has a node `comfydv`, imported from the ComfyUI Manager list under the placeholder publisher "Unclaimed". It has no versions. The maintainer claimed it for `darth-veitcher` on 2026-11-12.
- The `REGISTRY_ACCESS_TOKEN` repository secret holds the Comfy Registry key. The maintainer added it on 2026-11-12.
- The quality gate runs the unit tier only. The integration and system tiers need Ollama or Docker, which hosted CI does not have.
- `beacon doctor --strict` stays a local gate, because BEACON is not a project dependency.
- The first stable release after this spec is `0.2.0`, because the `[Unreleased]` entries contain new features.
- The docs site keeps its current deploy on each push to `main`.

## Non-Goals

- A `1.0.0` release. That is a separate decision.
- TestPyPI publishing.
- Release automation for the Docker images.
- Integration or system tests in hosted CI.
- A change to the default branch. This spec only collects the evidence and prepares the Registry entry.
