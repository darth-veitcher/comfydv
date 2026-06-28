---
description: Adversarial completeness audit of an epic's artefact tree (specs, stubs, tasks) against its stated intent — Success criteria, Non-goals, Dependencies, ADRs. The DESIGN-phase mirror of /beacon.review; use before building to confirm the epic is fully decomposed.
argument-hint: <epic-slug>  — e.g. "agent-loop" (omit to infer from the current spec branch)
allowed-tools: Task, Bash
---

You're auditing whether a BEACON epic is **fully decomposed** — whether its owned specs and stubs actually represent everything the epic's stated intent commits to. This is the prior question to `/beacon.review`: the reviewer checks a diff against the artefacts; this checks the artefacts against the intent.

## Step 1 — Resolve the epic slug

The argument is the **epic slug**:

$ARGUMENTS

If no slug was given, infer it: if the current branch matches `NNN-slug`, read `specs/<branch>/.beacon.toml` and use its `epic` field. If you still can't resolve one, run `beacon epic list` and ask the user which epic to audit — then STOP until they answer.

Verify the epic exists at `project-management/Roadmap/epics/<slug>.md`. If it doesn't, tell the user to create it first with `beacon epic new <slug> --title "<title>"` and STOP.

## Step 2 — Run the auditor in a fresh context

Use the **beacon-auditor** subagent. It reads the epic, the live `beacon epic refresh` rollup, and every owned spec/stub on its own terms — none of the reasoning that produced the current decomposition. That independence is the point.

Tell the subagent: *"Audit epic `<slug>` for completeness. Report only the epic's Success criteria that no owned spec or stub addresses, owned stubs still awaiting a real spec, filled specs missing tasks.md, and any owned spec that drifts from a Non-goal / ADR / unmet Dependency. Pair each finding with the exact `beacon epic stub` / `/beacon.specify` / `/beacon.tasks` command that closes it. Do not invent scope the epic never stated."*

## Step 3 — Return the report verbatim

Return the subagent's report exactly as written — don't summarise; the user reads it directly. The auditor only *suggests* commands; it creates nothing, so nothing in the tree changes from running this.

If the report ends with `Status: clear`, the epic's artefacts fully cover its stated intent — it's ready to build. Otherwise the user decides which suggested stubs to create (`beacon epic stub …`) or specs to fill (`/beacon.specify …`).
