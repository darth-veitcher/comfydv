---
name: beacon-ship
description: BEACON SHIP phase — promote validated DEV work to PROD, extract wisdom, and clean the transient workspace. Use when all bullets are complete or the user says "Ready to ship" / "Release this".
---

# Phase 4: SHIP — Release and extract wisdom

**Purpose:** Promote validated DEV work to PROD, document what was learned, and clean the transient workspace.

**Entry triggers:** All bullets complete / "Ready to ship" / "Release this"

**Tool:** `/git:release`

---

## SHIP checklist

### Before opening the release PR

- [ ] All bullets in `tasks.md` are marked complete
- [ ] All tests pass on `develop`
- [ ] Last CI run on `develop` is green (`gh run list --branch develop --limit 3`)
- [ ] Features have been validated in the DEV environment by a human
- [ ] `beacon doctor --strict` exits 0
- [ ] No known regressions
- [ ] **Documentation pass** (see below)
- [ ] Azure DevOps work items updated (Done/Closed) — use `@azure-devops-agent`

### Documentation pass — the external surface

Internal rigor (specs, ADRs, tests) doesn't help a stranger pick the project
up. Before shipping, check the user-facing surface — BEACON organises it with
[Diátaxis](https://diataxis.fr/) (tutorials / how-to / reference / explanation):

- [ ] **README** orients a newcomer: what-is-this, install, quickstart, a link out
- [ ] **CHANGELOG** has an `Unreleased` section capturing this release's notable changes
- [ ] **Public API** is real: the package root re-exports its surface (`__all__` / docstring), not empty
- [ ] **`pyproject [project.urls]`** points to the repo + docs
- [ ] **Which Diátaxis quadrant** did this change touch — and is there drift between quadrants (a how-to creeping into tutorial voice, a reference page lagging its code)?
- [ ] `beacon docs verify` is green (executable `# beacon:test` tutorial snippets still run)

`beacon doctor` enforces the mechanical floor of the above
(`readme-completeness`, `changelog-maintenance`, `changelog-vs-commits`,
`public-api-docs`, `project-urls`, `docs-freshness`, opt-in `diataxis-coverage`).

### Open the release PR

Run `/git:release` — this:
1. Checks DEV CI is green
2. Generates a changelog from Conventional Commits since last release
3. Opens a `develop → main` PR using `.github/PULL_REQUEST_TEMPLATE/release.md`

The PR requires a human approval in GitHub Actions (configured in Settings → Environments → prod).

### After the PR merges

1. **Tag the release:**
   ```bash
   git checkout main && git pull
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```

2. **Clean `Work/`** — transient notes belong in git history, not the repo:
   ```bash
   cd project-management/Work
   rm -rf sessions/*    # session notes are in git history
   rm -rf planning/*    # keep only active WIP
   rm -rf analysis/*    # promote to ADRs or delete
   ```

3. **Promote insights** — before deleting, check:
   - Did any session note contain a decision? → Write an ADR.
   - Did any analysis reveal a pattern worth keeping? → Add to Background/.

4. **Retrospective** (optional but valuable):
   Create `project-management/Work/analysis/retro-vX.Y.Z.md` with:
   - What worked well
   - What was harder than expected
   - One thing to do differently next time
   Then promote the worthwhile parts to ADRs and delete the file.

5. **Update Roadmap** — archive the current roadmap, start fresh:
   ```bash
   mv project-management/Roadmap/README.md \
      project-management/Roadmap/archive/vX.Y.Z-$(date +%Y-%m-%d).md
   # Create new README.md for next release
   ```

6. **Close any completed epic** — if this release shipped an epic's last spec,
   audit it, then archive it:
   ```bash
   /beacon.audit <slug>          # confirm every Success criterion was actually shipped
   beacon epic finish <slug>     # archive (refuses while a stub or live branch remains)
   ```
   The audit is a default-on *ship* moment — the `auto-audit` hook also nudges
   you right before `beacon epic finish`. It catches a Success criterion that no
   spec ever covered, which the deterministic placeholder gate can't see.

---

## The SHIP test

Before calling it done, answer:
- Does it work end-to-end in PROD?
- Is the code something you'd be proud to show a colleague?
- Could the next person understand what was built and why?

If no to any of these, it is not shipped — it is just deployed.
