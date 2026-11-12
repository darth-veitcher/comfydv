# Epic: Release Pipeline & Distribution

<!-- Write this epic to section 7 of docs/WRITING.md (ASD-STE100). -->

## Status
Planning  — started 2026-11-12

## Why now
comfydv has no releases. It has no git tags, no CI gate and no publish step.
ComfyUI-Manager installs the default branch with `git clone`. Thus each merge to
`main` goes to all users at once.

The next two epics make breaking changes: the node rename and the agent harness.
They must reach users as versioned releases with a changelog. They must not reach
users as silent changes to a branch. This epic is first because all later work
ships through it.

## Specs
_SpecKit specs that contribute to this epic. `beacon specify --epic <slug>`
links them. Otherwise, add each one by hand after you run `/speckit-specify`._

- specs/010-release-pipeline/ — Release Pipeline and Distribution

## ADRs
- A release ADR records the channel model below, when the spec starts.
- [ADR-003](../../ADRs/ADR-003-requirements-txt-authoring-policy.md) — `requirements.txt` stays hand-written.

## Channel model (maintainer decisions, 2026-11-12)

| Branch | Publishes | Version | Who gets it |
|---|---|---|---|
| `main` | git tag, GitHub Release, PyPI, Comfy Registry | `0.3.0` | All users |
| `develop` | git tag, PyPI pre-release | `0.3.0.dev1` | The maintainer, by opt-in |

- Dev builds go to PyPI as pre-releases, not to TestPyPI. pip and uv skip a
  pre-release unless the user asks for it with `--pre` or an exact version.
- The Comfy Registry gets stable releases only. Its docs require a static semver
  `version` and do not describe pre-releases.

### ComfyUI-Manager channels

ComfyUI-Manager shows two kinds of version for a Registry node:

- **latest** and numbered versions: releases published to the Registry. The docs
  call these "equivalent to stable releases".
- **nightly**: "the latest version updated by authors to github, equivalent to
  development version". ComfyUI's default security level blocks it, so a user
  must opt in.

The docs do not say which branch nightly clones. We infer the default branch.
Proposal: when comfydv is on the Registry, set `develop` as the GitHub default
branch. Then the Manager channels map to ours:

| Manager channel | comfydv source |
|---|---|
| latest, `0.3.0`, … | Registry release from `main` |
| nightly | `develop` HEAD |

Verify the inference before the change: install nightly in a test ComfyUI and
check the branch that it clones. Until then, `main` stays the default branch.
The legacy `custom-node-list.json` entry clones the default branch. Move it to
the Registry entry before the switch.

## Success criteria
- A CI gate runs `ruff check`, `ruff format --check`, `ty check` and the unit
  tests on each PR to `develop` and to `main`. A failure blocks the merge.
- A merge to `develop` publishes a PyPI pre-release. `pip install comfydv` still
  installs the last stable release.
- A merge to `main` creates a tag, a GitHub Release and a changelog entry. It
  publishes to PyPI and to the Comfy Registry.
- `pyproject.toml` has a static `version`. python-semantic-release increments it
  from Conventional Commits.
- ComfyUI-Manager shows comfydv "latest" as the last `main` release.
- The nightly-to-`develop` mapping is verified or rejected, with evidence.

## Non-goals
- A `1.0.0` release. That is a separate decision.
- TestPyPI publishing.
- Release automation for the Docker images.

## Notes
One-time setup that only the maintainer can do:
- ✅ Add a PyPI Trusted Publisher for `release.yml` with the environment `pypi` (2026-11-12).
- ✅ Create the GitHub environment `pypi` (2026-11-12).
- ✅ Create a Comfy Registry publisher: `darth-veitcher` (2026-11-12).
- ✅ Add its key as the `REGISTRY_ACCESS_TOKEN` repository secret (2026-11-12).
- ✅ Claim the existing Registry node `comfydv` for `darth-veitcher` (2026-11-12). The publisher's node list shows it.
- ✅ Add branch protection to `main` and `develop`, as GitHub rulesets (2026-11-12).
- Add the CI check as a required status check in both rulesets, when the plan names the check.

Design detail: `project-management/Work/analysis/llm-agent-harness.md` §8.
