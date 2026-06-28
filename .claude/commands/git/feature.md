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

The project uses **main** as the integration branch and **main** as the
stable / release branch. (If those names are the same, this project is on
trunk-based git flow — feature branches merge straight to `main` and
releases happen via tags on `main`.)

## Hotfix exception

If this is a **production-critical fix** that cannot wait for the next release:
- Cut from `main` instead: `git checkout main && git pull && git checkout -b fix/[slug]`
- PR to `main` directly
- If `main` and `main` differ (gitflow), immediately cherry-pick to `main` after merge:
  `git checkout main && git cherry-pick <sha>`
- Tell the user if this appears to be a hotfix based on the description
