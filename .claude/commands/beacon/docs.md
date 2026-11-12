---
description: Write or update documentation to the writing standard (docs/WRITING.md, ASD-STE100) with the beacon-docs procedure, then review it in a fresh beacon-docs-reviewer context. Pass `review` to run only the review.
argument-hint: [review] [files or topic]  — e.g. "README.md docs/how-to/export.md", "the new --watch option", or "review"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Task
---

You write or update documentation to the writing standard in `docs/WRITING.md`. The user's invocation:

$ARGUMENTS

## If the first word is `review`

Do not write anything. Use the **beacon-docs-reviewer** subagent for one full review of the documentation that changed on this branch. Give it the base branch and the list of changed Markdown files. If the user named files, give it only those files. If the user wrote "fixes only", tell the subagent "fixes only" and give it the diff of the fixes.

Return the report of the subagent without changes. Do not summarise it, because the user reads it directly.

## Otherwise: write, then review

1. **Use the `beacon-docs` skill.** Follow its procedure in sequence. Read, make the fact list and list the faults. Run `beacon docs check`, write the change and run each example. Make sure that no fact is lost.
   - If the user named files, those files are in scope.
   - If the user named a change or a topic, find the text that it touches. That is the `README.md` sections, the `docs/` pages, the `AGENTS.md` sections and the `--help` text.
   - If the user named nothing, the scope is the documentation that the current branch changes, and the documentation for the code that it changes.
2. **Ask for one full review.** Use the **beacon-docs-reviewer** subagent in a new context, as step 8 of the skill says. Give it the base branch and the list of changed files. Do not give it your fault list.
3. **Apply or reject each finding.** Verify each finding against the code, the command help and the tests. Apply each correct finding. Reject each wrong finding, with a reason. Run `beacon docs check` again, and commit the fixes.
4. **Ask for one fixes-only review.** Tell the subagent "fixes only", and give it the diff of the fixes. Apply or reject its findings as in step 3. Then stop. Do not run more passes.

If a pass stops before it is complete, record the part that it did not check, and say so in the report.

## Report

End with these items:

- The files that you changed.
- The result of `beacon docs check`, before and after.
- Each example that you ran, and each example that cannot run here, with the reason.
- Each fact that you removed because it is false.
- The findings of the two reviews: each finding that you applied, and each finding that you rejected, with the reason.
- Each part that a review did not check, with the cause.
