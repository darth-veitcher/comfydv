---
description: Adversarial review of the current diff against the parent epic + spec, in a fresh subagent context. Use before opening a PR.
argument-hint: (no arguments — reviews HEAD vs the integration branch)
allowed-tools: Task
---

Use the **beacon-reviewer** subagent to review the current diff.

The reviewer runs in a fresh context — it sees the diff, the spec, and the parent epic, but none of the reasoning that produced the change. That independence is the point: it evaluates the work on its own terms.

Tell the subagent: *"Review the current diff for BEACON correctness. Report only gaps tied to spec tasks, epic Success criteria, Non-goals, or linked ADRs — not style or hypothetical edges."*

Return the subagent's report verbatim. Don't summarise; the user will read it directly.

If the report ends with `Status: clear`, you're done. Otherwise the user decides which findings to address.
