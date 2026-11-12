# Future features

Ideas and follow-ups that are outside the scope of the current work.

## Docs site version label lags one release (from spec 010 converge, 2026-11-12)

`.github/workflows/docs.yml` runs on the push that merges a release pull request into `main`. That
push comes before PSR's release commit. PSR pushes with `GITHUB_TOKEN`, and a push with
`GITHUB_TOKEN` starts no workflows. So the docs site labels release `0.2.0` as `0.1.0`. Fix: deploy
the docs from `release.yml` after the release step, or run `docs.yml` on `push: tags: ["v*"]`.
