# ADR-017: Release channels and pipeline: PSR on gitflow, PyPI pre-releases, Registry stable only

## Status

> Accepted

_Date:_ 2026-11-12
_Deciders:_ darth-veitcher

---

## Context

comfydv has no releases. ComfyUI Manager clones the default branch, so each merge to `main` goes to
all users at once. The maintainer chose these points on 2026-11-12:

- `develop` for development, and `main` for releases (gitflow).
- Pre-releases on PyPI, not on TestPyPI.
- A clean break for the node rename, which needs a versioned release.

The Comfy Registry reads a static semver `version` from `pyproject.toml`. Its docs say nothing about
pre-releases. ComfyUI Manager shows Registry versions as "latest", and a git branch as "nightly".

## Decision

Release comfydv with python-semantic-release on GitHub Actions, from two branches.

| Branch | Version | Publishes |
|---|---|---|
| `main` | `X.Y.Z` | Release commit, tag, `CHANGELOG.md`, GitHub Release, PyPI, Comfy Registry |
| `develop` | `X.Y.Z.devN` | Tag and PyPI pre-release only. No commit on `develop` |

- Start from BEACON's `gitflow` release integration. Change it in two places: `develop` publishes to
  PyPI, not TestPyPI, and `main` also publishes to the Comfy Registry.
- Replace `hatch-vcs` with a static `version` in `pyproject.toml`. PSR increments it.
- Add the GitHub Actions integration as a push-only bypass actor in the `main` and `develop`
  rulesets. Only the release workflow has `contents: write`.
- A `quality-gate` check, required by both rulesets, runs lint, format, type and unit tests on each
  pull request.
- Change the default branch only after a recorded check of ComfyUI Manager "nightly".

## Consequences

**Easier:**
- Users get only versioned releases, with a changelog.
- The maintainer can test a pre-release with `pip install --pre comfydv`.
- No PyPI token exists. The Comfy Registry key is the only publishing secret.

**Harder / constrained:**
- Commit messages decide the version, so a wrong commit type gives a wrong version.
- A workflow with `contents: write` can push to `main` through the bypass. Keep that permission in
  `release.yml` only. Move to a GitHub App if a second workflow needs it.
- `pyproject.toml` on `develop` holds the last stable version, not the pre-release version.

## Considered Alternatives

### Alternative A: TestPyPI for pre-releases (BEACON's default)

**Why rejected:** TestPyPI does not host the dependencies. An install needs a second index, and that
is open to dependency confusion.

### Alternative B: Pre-releases on the Comfy Registry

**Why rejected:** The Registry docs do not describe pre-releases, and ComfyUI Manager could offer
them to all users.

### Alternative C: Trunk-based releases from tags on `main`

**Why rejected:** The maintainer wants to test each change before it reaches users. On trunk, each
merge to `main` reaches the users who clone the default branch.

---

## Links

- Spec: `specs/010-release-pipeline/` (research R1 to R14)
- Related ADRs: [ADR-003](ADR-003-requirements-txt-authoring-policy.md)
