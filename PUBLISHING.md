<!-- BEACON git_flow: gitflow -->

# Publishing `comfydv`

This guide is for the maintainer. It tells you how the workflow makes a release, and what to set
up one time.

The workflow [`.github/workflows/release.yml`](.github/workflows/release.yml) runs on each push to
`main` and to `develop`. [python-semantic-release][psr] (PSR) calculates the version. The decision
record is [ADR-017](project-management/ADRs/ADR-017-release-channels-and-pipeline.md).

| Branch | Publishes to | Version | When |
|---|---|---|---|
| `main` | [PyPI](https://pypi.org/project/comfydv/) and the [Comfy Registry](https://registry.comfy.org/nodes/comfydv) | `0.2.0`, `0.3.0`, … | A merge from `develop` that has a `feat:`, `fix:` or `perf:` commit |
| `develop` | PyPI, as a pre-release | `0.2.0.dev1`, `0.2.0.dev2`, … | A merge that has a `feat:`, `fix:` or `perf:` commit |

pip and uv install a pre-release only when you ask for one, or when PyPI has no stable version of
comfydv yet. After the first stable release, users get only stable releases.

## Release a new version

1. Merge your pull requests into `develop`. Each merge with a `feat:`, `fix:` or `perf:` commit
   publishes a pre-release to PyPI.
2. To test a development build in ComfyUI, use an install that you made with `git clone`. Run
   `git checkout develop` in `custom_nodes/comfydv`. Then run `pip install -r requirements.txt` again.
   ComfyUI does not load nodes from a package that pip installs.
3. Run `/git:release` to open the pull request from `develop` to `main`.
4. Merge it with a merge commit, not a squash. PSR takes the type of each commit from its first line.
   A squash makes one commit, and its first line is the pull request title.

The workflow releases, then merges `main` back into `develop`. Do not edit the version or
`CHANGELOG.md` by hand.

## Predict the next version

PSR reads the Conventional Commits since the last tag. The commit type with the largest effect sets
the version change:

| Commit | Version change |
|---|---|
| `BREAKING CHANGE:` in the footer | minor while the version is 0.x (`major_on_zero = false`), then major |
| `feat:` | minor (0.X.0) |
| `fix:` or `perf:` | patch (0.X.Y) |
| Only `docs:`, `chore:`, `ci:`, `test:`, `style:`, `refactor:`, `build:` or `revert:` | no release |

On `main`, the workflow does these steps:

1. Calculate the next version.
2. Write it to `[project] version` in `pyproject.toml`.
3. Add an entry to `CHANGELOG.md`, directly under the `<!-- version list -->` marker.
4. Commit `chore(release): X.Y.Z`, and tag `vX.Y.Z`.
5. Build the wheel and the sdist with `uv build`.
6. Publish to PyPI, and create a GitHub Release with both files.
7. Publish to the Comfy Registry, then check that the Registry lists the new version.
8. Merge `main` into `develop`.

On `develop`, the workflow tags `vX.Y.Z-dev.N` and publishes to PyPI. It writes no commit. Because of this, the version in `pyproject.toml` and the release entries in `CHANGELOG.md` on `develop` stay the same as
on `main`.

## Set up the pipeline one time

### Done on 2026-11-12

- **PyPI Trusted Publisher** at https://pypi.org/manage/account/publishing/: project `comfydv`,
  owner `darth-veitcher`, repository `comfydv`, workflow `release.yml`, environment `pypi`. It stays
  "pending" until the first publish.
- **GitHub environment** `pypi`. Both branches use it. Do not add "Required reviewers" to it: then
  each merge to `develop` waits for your approval.
- **Comfy Registry publisher** `darth-veitcher`, with the node `comfydv` claimed. The publisher ID and
  the node ID cannot change.
- **Repository secret** `REGISTRY_ACCESS_TOKEN`: the Comfy Registry key. PyPI needs no token.
- **Branch rulesets** on `main` and `develop`.

### Done on 2026-11-13

- **The workflow can push.** The release pushes its commit and tag to `main`, and it merges `main`
  into `develop`. The rulesets require pull requests. A personal repository cannot add GitHub
  Actions as a bypass actor, so the release pushes with a token of the owner:
  - Each ruleset has the bypass actor **Repository admin**.
  - The repository secret `GH_TOKEN` holds a fine-grained personal access token of the owner. It
    has access to `comfydv` only, with **Contents: Read and write**.
  - `release.yml` uses `GH_TOKEN` for the checkout, for PSR and for the push to `develop`.
- **A release push does not start a new release.** A push with a personal access token starts the
  workflows again. `release.yml` does not run for a push whose commit message starts with
  `chore(release):`. Both release pushes start with it.

### Still to do

1. **Require the quality gate.** In each ruleset, add the status check `quality-gate`. The list
   shows it after `ci.yml` runs one time on a pull request.

## Check a release

```bash
pip index versions --pre comfydv                             # all the versions on PyPI, with the pre-releases
pip install comfydv                                          # the last stable release
pip install --pre comfydv                                    # the last pre-release
curl -s https://api.comfy.org/nodes/comfydv/versions         # the versions on the Comfy Registry
```

## Fix a failed release

- **PyPI rejects the upload.** Look at the Trusted Publisher fields. They must match the fields in
  "Done on 2026-11-12" exactly.
- **The Comfy Registry step fails.** Look at the `REGISTRY_ACCESS_TOKEN` secret. Then, in GitHub
  Actions, open the **Release** workflow and select **Run workflow** on `main`. Select the check box
  **Publish the version on main to the Comfy Registry again**. You can also run
  `gh workflow run release.yml --ref main -f publish_registry=true`. A plain re-run does not work,
  because PSR finds the tag and releases nothing.
- **GitHub rejects the push to `main` or `develop`.** Look at the `GH_TOKEN` secret. The token
  can expire. Make a new token with the same access, then run
  `gh secret set GH_TOKEN -R darth-veitcher/comfydv` and paste it at the prompt.

[psr]: https://python-semantic-release.readthedocs.io/
