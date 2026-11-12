---
description: Open a develop→main release PR. This is the human sign-off gate before PROD. Generates a changelog from Conventional Commits since the last release.
argument-hint: [release-title or version] — e.g. "v1.2.0" or "Q2 sprint 3"
allowed-tools: Bash, Read, Grep
---

Open a release PR: develop → main.

# Release PR (develop → main)

This command is the **PROD promotion gate** for the gitflow branching model. It aggregates everything validated in DEV into a single reviewable PR. A human approves it; GitHub Actions then deploys to PROD.

## 1. Pre-flight checks

```bash
# Ensure develop is up to date
git fetch origin
git checkout develop
git pull origin develop

# Confirm CI is green on develop
gh run list --branch develop --limit 5
```

If the last CI run on develop failed: **stop and report**. Do not open a release PR against a broken develop.

## 2. Determine version / release title

If `$ARGUMENTS` is provided, use it as the release title.
Otherwise, suggest a version by inspecting the most recent git tag:

```bash
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
echo "Last release: $LAST_TAG"
# Suggest next patch/minor based on commit types since last tag
git log "$LAST_TAG"..develop --oneline
```

Suggest versioning based on Conventional Commits since last tag:
- Any `feat:` commit → minor bump
- Only `fix:` / `chore:` → patch bump
- `BREAKING CHANGE` in footer → major bump

## 3. Generate changelog

```bash
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
BASE="${LAST_TAG:-$(git rev-list --max-parents=0 HEAD)}"

echo "## What's changed"
echo ""
echo "### Features"
git log "$BASE"..develop --oneline --grep="^feat" | sed 's/^/- /'
echo ""
echo "### Fixes"
git log "$BASE"..develop --oneline --grep="^fix" | sed 's/^/- /'
echo ""
echo "### Other"
git log "$BASE"..develop --oneline --grep="^chore\|^docs\|^refactor\|^test\|^ci" | sed 's/^/- /'
```

## 4. Check Work/ cleanup

Look in `project-management/Work/sessions/` and `Work/planning/`:
- If stale session files exist (older than current sprint): remind user to clean them before release
- Output: "⚠ Stale Work/ files found — clean up before merging (see project-management/Work/README.md)"

## 5. Open the PR

Use `.github/PULL_REQUEST_TEMPLATE/release.md` as the structure.

```bash
TITLE="${ARGUMENTS:-Release $(date +%Y-%m-%d)}"

gh pr create \
  --title "$TITLE" \
  --base main \
  --head develop \
  --body-file /tmp/release-pr-body.md \
  --label "release"
```

## 6. After creating

Report:
- PR URL
- Commits included (count)
- Any ADRs created in this release cycle
- Reminder: after merge, tag `main` with the version:
  ```bash
  git checkout main && git pull
  git tag -a v1.2.0 -m "Release v1.2.0"
  git push origin v1.2.0
  ```
- Reminder: clean `project-management/Work/` after merge:
  ```bash
  cd project-management/Work
  rm -rf sessions/* planning/*  # keep only active WIP
  ```

## Branch model

```
main    ← PROD  ← this PR (human approval + CI gate in GitHub Actions)
  ↑
develop ← DEV   (auto-deploys; validated here first)
```
