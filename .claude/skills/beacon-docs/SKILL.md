---
name: beacon-docs
description: Write or update documentation to the writing standard in docs/WRITING.md (ASD-STE100 Simplified Technical English plus project rules). Use when the user asks to write, rewrite, fix or review README.md, docs/, AGENTS.md, the --help text of a command, an ADR, an epic, a spec or a plan — and after any change that a user can see, because that change also changes README.md or docs/.
---

# Write documentation to the standard

**Purpose:** Make the documentation correct for its reader, in Simplified Technical English, with no fact lost.

**The standard:** `docs/WRITING.md`. Read all of it before you start. Section 1 sets the reader of each file and of the `--help` text. Sections 2 and 3 give the writing rules. Sections 4 and 5 give the structure of `README.md` and of `AGENTS.md`. Section 6 gives the check and the review, and section 7 gives the rules for ADRs, epics, specs and plans. Rules 2, 6 and 7 apply to the `--help` text of each command and option.

Do this procedure in sequence. Do not skip a step. Write your report in ASD-STE100.

## 1. Read the files and the code

1. Name the files in scope. For a feature change, that is `README.md`, the pages in `docs/` that the change touches, and `AGENTS.md` if a command or rule changed. If a command or an option changed, its `--help` text is in scope too.
2. Read each file from start to end.
3. If the project has API contracts in `specs/*/contracts/`, read the contracts that the text describes. The "Technical notes" section of `README.md` links to them.
4. Read the code for each claim that you will write. Do not write behaviour that you did not find in the code, in the command help or in a contract.

## 2. Make the fact list

Write one line for each fact that the old text gives. A fact is a command, an option, a value, a limit, a platform note, a name or a link. You use this list in step 7.

## 3. List the faults

Write one line for each fault: the file, the line, the rule number in `docs/WRITING.md`, and the fix. Use this list as your work plan. Look for these faults:

- A section that starts with the mechanism, not the task (rule 8).
- A topic for all the tasks, such as errors or provenance, with a heading that is not a task name (rule 12).
- A specialist term with no explanation and no glossary entry (rule 6).
- A result value with no meaning in practice: no usual range, no "higher means" (rule 9).
- An internal planning label in `README.md` or `docs/`, or a link to an ADR or an API contract outside "Technical notes" (rule 7).
- History in `README.md` or `AGENTS.md` (rule 11).
- A missing part of the structure in section 4 or section 5. Examples: a task with no row in the "What you can do" table, or a "Quickstart" that is not one complete example.
- An example that no test runs and that is not in the list of examples that no test runs (rule 10).
- A statement that the code no longer supports.
- A command or an option with no `--help` text, or `--help` text with a long sentence, an unexplained term or a planning label.
- A long sentence, a passive verb, or two instructions in one sentence (section 2).

## 4. Run the check

```bash
beacon docs check
```

It lists each finding as `file:line: rule: message`, and it counts them. Record the number of findings before you write. For an ADR, epic, spec or plan, name the file:

```bash
beacon docs check --file project-management/ADRs/ADR-007-example.md
```

For `--help` text, give each help text as one record, with its source name on the first line. A test of the project usually does this. By hand, it looks like this:

```bash
printf 'tool fetch --help\nDownload a pinned model.\n' | beacon docs check --text - --null
```

Add each result to the fault list from step 3.

## 5. Write the change

- Follow the structure in section 4 for `README.md` and in section 5 for `AGENTS.md`. Keep the fixed names of the `README.md` headings, because the doctor and the check look for them.
- Write each heading as a task that the reader does.
- Write one instruction in each sentence: 20 words or fewer for a procedure, 25 words or fewer for a description.
- Write one topic in each paragraph, with a maximum of six sentences.
- Use the same word for the same thing in all the files. Put each term in the glossary.
- Give each example the file names that a reader uses. Measure a value with the real code before you give its usual range, and write where the value comes from.
- Move detail that hides the main point into `docs/` or into **Technical notes**. Do not delete it.
- Do not edit `.claude/CLAUDE.md`, `docs/WRITING.md`, or the text between the BEACON markers in `AGENTS.md`. BEACON owns them.

## 6. Run each example and the checks

Run each command and each code block in the new text, exactly as written. `beacon docs verify` runs each Python code block that has the `# beacon:test` marker:

```bash
beacon docs verify
beacon docs check
```

Continue until the check reports 0 findings and each example runs. If an example needs a network, a GPU or a secret, it cannot run in a test. Add it to the list of examples that no test runs. Give the reason in that list and in your report (rule 10). If the project has a test that runs the `--help` text through `beacon docs check --text`, run it when a command or an option changes.

## 7. Make sure that no fact is lost

Compare the fact list from step 2 with the new text. Each fact must be in the new `README.md`, in a page in `docs/`, or in a **Technical notes** section. A fact for agents only can go in `AGENTS.md`. If a fact is now false, remove it and say so in your report. Do not remove a fact only because it is long.

## 8. Ask for a review

Do the review of section 6 of `docs/WRITING.md`: one full pass, then one pass for the fixes only. Do not run more passes.

1. Start the `beacon-docs-reviewer` agent in a new context. Give it the base of the change, for example `origin/main`, and the list of changed files. Do not give it your fault list, because it must read the result without your assumptions. From a terminal, use this form:

   ```bash
   claude -p "<prompt>" --agent beacon-docs-reviewer --allowedTools Read Grep Glob Bash
   ```

   The option `--allowedTools` takes all the values that follow it, so put the prompt before the options. If you cannot start that agent type, start a general agent with the text of `.claude/agents/beacon-docs-reviewer.md` as its instructions.
2. Verify each finding against the code, the command help and the tests. The reviewer can be wrong too.
3. Apply each correct finding. Reject each wrong finding, and write the reason.
4. Run step 6 again, and commit the fixes.
5. Start the agent one more time. Tell it "fixes only", and give it the diff of the fixes, for example `git diff <commit before the fixes>..HEAD`.
6. Apply or reject its findings as in items 2 to 4. Then stop.

A pass can stop before it is complete, for example because of a full disk or a limit of a tool. Then record the part that the pass did not check, and write it in your report. When the cause is not there any more, run that part again.

## 9. Report

Give these items:

- The number of check findings before and after.
- The fact list, with the place of each fact.
- Each example that you ran, and each example that cannot run, with the reason.
- The findings of the two review passes: the findings that you applied, and the findings that you rejected, each with its reason.
- Each part that a pass did not check, with the cause.

## Done when

- `beacon docs check` reports 0 findings.
- `beacon doctor --strict` passes.
- Each example ran, or the list of examples that no test runs gives its reason.
- Each fact in the fact list is in the new text, or the report says why it was removed.
- The full review and the fixes-only review are done, and each finding is applied or rejected with a reason.
