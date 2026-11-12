<!-- BEACON git_flow: gitflow -->

# Publishing `comfydv`

This guide is for the maintainer. It tells you how a release happens, and what to set up once.

The workflow [`.github/workflows/release.yml`](.github/workflows/release.yml) runs on each push to
`main` and to `develop`. [python-semantic-release][psr] (PSR) calculates the version. The decision
record is [ADR-017](project-management/ADRs/ADR-017-release-channels-and-pipeline.md).

| Branch | Publishes to | Version | How it starts |
|---|---|---|---|
| `main` | [PyPI](https://pypi.org/project/comfydv/) and the [Comfy Registry](https://registry.comfy.org/nodes/comfydv) | `0.2.0`, `0.3.0`, … | Merge the release pull request from `develop` |
| `develop` | PyPI, as a pre-release | `0.2.0.dev1`, `0.2.0.dev2`, … | Merge a pull request into `develop` |

pip and uv do not install a pre-release unless you ask for one, so users get only stable releases.

## Release a new version

1. Merge your pull requests into `develop`. Each merge with a `feat:`, `fix:` or `perf:` commit
   publishes a pre-release to PyPI.
2. To test a development build in ComfyUI, run `git checkout develop` in `custom_nodes/comfydv`.
   ComfyUI does not load nodes from a package that pip installs.
3. Run `/git:release` to open the pull request from `develop` to `main`.
4. Merge it. The workflow releases, then merges `main` back into `develop`.

You never edit the version or `CHANGELOG.md` by hand.

## How PSR calculates the version

PSR reads the Conventional Commits since the last tag. The strongest type decides the change:

| Commit | Version change |
|---|---|
| `BREAKING CHANGE:` in the footer | minor while the version is 0.x (`major_on_zero = false`), then major |
| `feat:` | minor (0.X.0) |
| `fix:` or `perf:` | patch (0.X.Y) |
| Only `docs:`, `chore:`, `ci:`, `test:`, `style:` or `refactor:` | no release |

On `main`, the workflow does these steps:

1. Calculate the next version.
2. Write it to `[project] version` in `pyproject.toml`.
3. Add an entry to `CHANGELOG.md`, above the `<!-- version list -->` marker.
4. Commit `chore(release): X.Y.Z`, and tag `vX.Y.Z`.
5. Build the wheel and the sdist with `uv build`.
6. Publish to PyPI, and create a GitHub Release with both files.
7. Publish to the Comfy Registry, then check that the Registry lists the new version.
8. Merge `main` into `develop`.

On `develop`, the workflow tags `vX.Y.Z-dev.N` and publishes to PyPI. It writes no commit, so
`pyproject.toml` and `CHANGELOG.md` on `develop` stay equal to `main`.

## One-time setup

### Done on 2026-11-12

- **PyPI Trusted Publisher** at https://pypi.org/manage/account/publishing/: project `comfydv`,
  owner `darth-veitcher`, repository `comfydv`, workflow `release.yml`, environment `pypi`. It stays
  "pending" until the first publish.
- **GitHub environment** `pypi`. Both branches use it. Do not add "Required reviewers" to it: then
  each merge to `develop` waits for your approval.
- **Comfy Registry publisher** `darth-veitcher`, with the node `comfydv` claimed. The publisher ID and
  the node ID cannot change.
- **Repository secret** `REGISTRY_ACCESS_TOKEN`: the Comfy Registry key. It is the only publishing
  secret. PyPI needs no token.
- **Branch rulesets** on `main` and `develop`.

### Still to do

1. **Let the workflow push.** The release pushes its commit and tag to `main`, and it merges `main`
   into `develop`. Your rulesets require pull requests, so they block these pushes. In each ruleset,
   add **GitHub Actions** as a bypass actor. Only `release.yml` has `contents: write`, and `ci.yml`
   can only read.
2. **Require the quality gate.** In each ruleset, add the status check `quality-gate`. It appears in
   the list after `ci.yml` runs once on a pull request.

## Check a release

```bash
pip index versions comfydv                                   # the versions on PyPI
pip install comfydv                                          # the last stable release
pip install --pre comfydv                                    # the last pre-release
curl -s https://api.comfy.org/nodes/comfydv/versions         # the versions on the Comfy Registry
```

## When a release fails

- **PyPI rejects the upload.** Look at the Trusted Publisher fields. They must match the table above exactly.
- **The Comfy Registry step fails.** Look at the `REGISTRY_ACCESS_TOKEN` secret. To try again, run
  the failed workflow again. PyPI skips a version that it already has.
- **The push to `main` or `develop` is refused.** Add the bypass actor (step 1 above).

[psr]: https://python-semantic-release.readthedocs.io/
