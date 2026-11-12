# ADR-016: Constitution 1.1.0: add the documentation article

## Status

> Accepted

_Date:_ 2026-11-12
_Deciders:_ darth-veitcher

---

## Context

BEACON 1.18 installs a writing standard, `docs/WRITING.md`. Section 6 of the standard says that
the constitution must have an article "Documentation for people and for agents". With that
article, the Constitution Check of each plan includes the documentation.

The constitution (1.0.0) had no such article. Its Governance section requires an ADR for each
amendment. Rule 19 of the standard says that each constitution article is a set of MUST or MUST NOT
rules. Each rule has a reason in one sentence. Version 1.0.0 did not obey rule 19.

## Decision

Amend the constitution to version 1.1.0, with a new Article VII "Documentation for People and for
Agents", and write all articles to rule 19.

- **Article VII** requires that `README.md`, `docs/`, `AGENTS.md` and the artefacts follow
  `docs/WRITING.md`. A change that a user can see changes the docs in the same pull request.
  `beacon docs check` and `beacon doctor --strict` pass, and a review checks the words.
- **Articles I to VI** keep their meaning. Each one is now a list of MUST rules with a reason.
- **Two rules are now explicit.** Article III names `folder_paths` with `comfy.*` and `server.*`,
  because the code already guards it. Article VI forbids moving an output of a released node.
  Version 1.0.0 said "immutable" for the same rule.
- **Governance** now states the semantic-versioning policy.

The version is MINOR (1.0.0 → 1.1.0) because the amendment adds an article.

### Sync impact report

| Item | Change |
|---|---|
| Version | 1.0.0 → 1.1.0 |
| Principles renamed | None |
| Principles changed | I to VI: wording only, to rule 19 of the standard |
| Sections added | Article VII "Documentation for People and for Agents" |
| Sections removed | None |
| Placeholders deferred | None |

## Consequences

**Easier:**
- The plan gate of each spec checks the documentation, so a spec cannot omit its README change.
- Each rule gives its reason, so a reviewer can judge an exception.

**Harder / constrained:**
- Each pull request that changes behaviour that a user can see also needs a docs change and a review.

**Migration note:** No code changes. Existing specs and plans keep their text. Each new spec, plan
and tasks file follows the standard.

## Considered Alternatives

### Alternative A: Add Article VII, and keep the old wording of Articles I to VI

**Why rejected:** Rule 19 applies to each new version of the constitution. A new version with old
wording would fail the standard that its own Article VII requires.

### Alternative B: Put the documentation rules in `AGENTS.md` only

**Why rejected:** The plan gate reads the constitution, not `AGENTS.md`. The rules would have no
effect on plans.

---

## Links

- Constitution: `.specify/memory/constitution.md`
- Standard: `docs/WRITING.md`, sections 6 and 7
