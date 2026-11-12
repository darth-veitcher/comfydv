# Data Model: Release Pipeline and Distribution

The feature has no database. Its entities are versions, tags, packages and checks.

## Release

A stable version of comfydv, from `main`.

| Field | Source | Rule |
|---|---|---|
| `version` | PSR, from the commits since the last tag | `X.Y.Z`, semver and PEP 440 (FR-006 to FR-009) |
| `tag` | PSR | `vX.Y.Z` (FR-012) |
| `changelog_entry` | PSR, `CHANGELOG.md` | The changes, grouped by commit type (FR-013) |
| `github_release` | PSR `publish` | Has the changelog entry, the wheel and the sdist (FR-014) |
| `pypi_package` | `pypa/gh-action-pypi-publish` | Same `version` (FR-015) |
| `registry_version` | `Comfy-Org/publish-node-action` | Same `version`, in node `comfydv` (FR-016) |

## Pre-release

A development version of comfydv, from `develop`.

| Field | Source | Rule |
|---|---|---|
| `version` | PSR, `prerelease_token = "dev"` | `X.Y.Z-dev.N`, which PEP 440 makes `X.Y.Z.devN` (FR-011) |
| `tag` | PSR | `vX.Y.Z-dev.N`. The tag is on `develop`, with no release commit (FR-020) |
| `pypi_package` | `pypa/gh-action-pypi-publish` | Same `version` (FR-018) |

A pre-release has no changelog entry and no Registry version (FR-019).

## Channel

A place that a user installs from.

| Channel | Gets | How a user selects it |
|---|---|---|
| PyPI stable | Each Release | `pip install comfydv` |
| PyPI pre-release | Each Pre-release | `pip install --pre comfydv`, or an exact `==X.Y.Z.devN` |
| Comfy Registry "latest" | Each Release | ComfyUI Manager, with no change to the defaults |
| ComfyUI Manager "nightly" | A git branch. Unknown until the check in `quickstart.md` | Manager, after the user lowers `security_level` |

## Quality gate

| Field | Value |
|---|---|
| Workflow | `.github/workflows/ci.yml` |
| Trigger | `pull_request` to `develop` or `main` |
| Required check name | `quality-gate` |
| Matrix | Python 3.11, 3.12, 3.13 |
| Steps | `ruff check`, `ruff format --check`, `ty check`, unit tests |
| Permissions | `contents: read`. No secrets. |

## Version state

```text
            feat:/fix:/perf:/BREAKING on develop
 vA.B.C ─────────────────────────────────────▶ vA.(B+1).0-dev.1 ─▶ -dev.2 ─▶ …   (pre-releases, tags only)
   │
   │        release PR develop → main (same commits)
   └─────────────────────────────────────────▶ vA.(B+1).0                          (release commit + tag on main)
                                                   │
                                                   └─▶ merge main into develop (FR-017)
```

The bump depends on the strongest commit type since the last stable tag:

| Strongest commit type | While major is 0 | From 1.0.0 |
|---|---|---|
| `BREAKING CHANGE` | minor | major |
| `feat` | minor | minor |
| `fix`, `perf` | patch | patch |
| Only `docs`, `chore`, `ci`, `test`, `style`, `refactor` | none | none |
