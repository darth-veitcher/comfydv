---
description: Tag main with the next version and push. CI publishes from the tag. Trunk-based projects don't need a promotion PR — main is always shippable.
argument-hint: [version] — e.g. "v1.2.0". Omit to suggest from Conventional Commits since the last tag.
allowed-tools: Bash, Read, Grep
---

Tag the next release on `main`.

# Release (trunk-based)

This project uses **trunk-based** git flow — `main` is always shippable, so a release is just a tag. CI takes it from there.

## 1. Pre-flight checks

```bash
# Ensure main is up to date
git fetch origin
git checkout main
git pull origin main

# Confirm CI is green on main
gh run list --branch main --limit 5
```

If the last CI run on main failed: **stop and report**. Do not tag a broken main.

## 2. Determine version

If `$ARGUMENTS` is provided, treat it as the explicit version (e.g. `v1.2.0`).
Otherwise, suggest a version by inspecting the most recent git tag and the Conventional Commits since:

```bash
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
echo "Last release: $LAST_TAG"
git log "$LAST_TAG"..HEAD --oneline
```

Apply Conventional Commits semver:
- `BREAKING CHANGE` in footer → major bump
- Any `feat:` → minor bump
- Only `fix:` / `perf:` / etc. → patch bump

If the project uses python-semantic-release (i.e. `beacon integration add release` was run), the PSR action on push already determines the version automatically — in that case you don't tag by hand; just push to `main`.

## 3. Generate release notes (preview)

```bash
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
BASE="${LAST_TAG:-$(git rev-list --max-parents=0 HEAD)}"

echo "## What's changed"
echo ""
echo "### Features"
git log "$BASE"..HEAD --oneline --grep="^feat" | sed 's/^/- /'
echo ""
echo "### Fixes"
git log "$BASE"..HEAD --oneline --grep="^fix" | sed 's/^/- /'
echo ""
echo "### Other"
git log "$BASE"..HEAD --oneline --grep="^chore\|^docs\|^refactor\|^test\|^ci" | sed 's/^/- /'
```

This preview gives you the changelog body; PSR (if installed) will generate the canonical version on push.

## 4. Check Work/ cleanup

Look in `project-management/Work/sessions/` and `Work/planning/`:
- If stale session files exist (older than current sprint): remind user to clean them before tagging
- Output: "⚠ Stale Work/ files found — clean up before releasing (see project-management/Work/README.md)"

## 5. Tag and push

```bash
VERSION="${ARGUMENTS:-v$(date +%Y.%m.%d)}"   # fallback to date-based if no arg

git tag -a "$VERSION" -m "Release $VERSION"
git push origin "$VERSION"
```

## 6. After tagging

Report:
- Tag created (version)
- Tag commit SHA
- Reminder: if `release` integration is installed, the GitHub Actions workflow now picks the tag up and publishes — `gh run list --branch main --limit 1` watches it.
- Reminder: clean `project-management/Work/` after release:
  ```bash
  cd project-management/Work
  rm -rf sessions/* planning/*  # keep only active WIP
  ```

## Branch model

```
main    ← integration AND release branch (trunk-based)
  ↑
feature/x ← merges here directly; main is always shippable
```

No develop, no promotion PR. Tag what's shippable; let CI ship it.
