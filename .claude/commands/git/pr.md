---
description: Open a pull request from the current branch to develop (default) or main (hotfix). Runs BEACON quality gates first and populates the description from the related spec.
argument-hint: [pr-title] — optional; inferred from branch name if omitted
allowed-tools: Bash, Read, Grep
---

Open a PR for the current branch.

# Pull Request

## 1. Detect context

```bash
BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Current branch: $BRANCH"
```

- If branch starts with `fix/` AND was cut from `main` (check `git log main..HEAD`): this is a **hotfix** — target `main`
- Otherwise: target **develop**

## 2. Run BEACON quality gates

Do not open a PR if any gate fails.

```bash
uv run ruff check --fix && uv run ruff format
uv run ty check
beacon doctor --strict   # semantic health — fails on placeholders, drift, stale notes
git diff --stat HEAD
```

If a gate fails: fix it before proceeding. Report what failed.

## 3. Find related spec and build PR body

Search `specs/` for a spec matching the branch name (strip prefix):

```bash
FEATURE=$(echo "$BRANCH" | sed 's|^[^/]*/||')
ls specs/ 2>/dev/null | grep -i "$FEATURE" | head -1
```

Build the PR body using:
- Specification summary from `spec.md` (user stories + acceptance criteria)
- Plan summary from `plan.md` (what changed architecturally)
- Task list from `tasks.md` (which bullets are complete)
- `git log develop..HEAD --oneline` (commits included)

Use `.github/PULL_REQUEST_TEMPLATE/feature.md` as the structure.

## 4. Open the PR

```bash
BASE="develop"   # or "main" for a hotfix
TITLE="${ARGUMENTS:-$(echo "$BRANCH" | sed 's|^[^/]*/||' | tr '-' ' ')}"

gh pr create \
  --title "$TITLE" \
  --base "$BASE" \
  --head "$BRANCH" \
  --body-file /tmp/pr-body.md
```

## 5. After creating

Report:
- PR URL
- Target branch and why
- Required CI checks that must pass
- If this is a hotfix to `main`: remind to cherry-pick it to `develop` after merge
