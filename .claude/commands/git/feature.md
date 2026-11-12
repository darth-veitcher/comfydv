---
description: Cut a branch from main for non-spec work (quick fixes, chores, docs). Spec work branches via /speckit-specify instead.
argument-hint: [branch-type/description] e.g. "fix/null-pointer" or "docs/update readme"
allowed-tools: Bash, Read, TodoWrite
---

Create a branch for: $ARGUMENTS

# Branch from main (non-spec work)

Use this for small changes that don't warrant a spec — bug fixes, chores, docs.

**Spec'd feature work does not use this command.** `/speckit-specify` creates
the spec branch (`NNN-slug`) as part of the DESIGN phase — run that instead.

## Steps

1. **Sync main:**
```bash
git fetch origin
git checkout main
git pull origin main
```

2. **Determine branch type and cut the branch:**
```bash
RAW="$ARGUMENTS"
# Strip existing prefix if user included one, then slugify
SLUG=$(echo "$RAW" | tr '[:upper:]' '[:lower:]' | sed 's|[^a-z0-9/]|-|g' | sed 's/--*/-/g' | sed 's/^-\|-$//g')
# Default to feature/ if no type prefix
if [[ "$SLUG" != fix/* && "$SLUG" != chore/* && "$SLUG" != docs/* ]]; then
  SLUG="feature/$SLUG"
fi
git checkout -b "$SLUG"
echo "✓ Created branch: $SLUG (from main)"
```

3. **Report** the branch name and base (`main`). PRs from this branch
   target `main` — use `/git:pr` when ready.

## Branch model reminder

This project is on trunk-based git flow: there is no `develop` branch. Feature
branches merge straight to `main`, and releases are tags on
`main` (`/git:release`). A hotfix follows the same path — branch
from `main`, PR to `main`, then tag.
