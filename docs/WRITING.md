# Writing standard

Version 3 (2026-10-28)

This standard tells you how to write the documentation, the `--help` text and the project artefacts in this repository. BEACON installs this file at `docs/WRITING.md`, and `beacon upgrade` replaces it. Do not edit it in a project. BEACON is the only source of this standard and of its check. To change the standard, change it in BEACON and increase the version.

## 1. Files and readers

| File | Reader | Contents |
|---|---|---|
| `README.md` | A person who uses the package or tool | What it does, how to install it, the tasks it does, with examples |
| `docs/` | The same person | Guides, tutorials and reference. Each page is about one task or one topic |
| CLI `--help` text | A person who uses the command | What each command and option does |
| `AGENTS.md` | An AI assistant that works in the repository | Commands, rules, the directory map, current work and known problems |
| `CLAUDE.md` (root) | Claude Code | `@AGENTS.md`, and only the instructions that apply to Claude alone |
| Project artefacts | The team, and the agents that plan and build the work | ADRs, epics, specs, plans, tasks and the constitution (section 7) |

Rules 2, 6 and 7 apply to the CLI `--help` text: the sentence length, the explanation of terms and no planning labels.

The standard does not apply to `CHANGELOG.md`, code comments, commit messages or generated files. They keep their own formats. Do not edit `.claude/CLAUDE.md`, because BEACON owns it and `beacon upgrade` replaces it. For the same reason, do not edit the text between `<!-- BEACON START -->` and `<!-- BEACON END -->` in `AGENTS.md`.

## 2. Writing rules (ASD-STE100)

1. Use the approved words with their approved meanings. You can use the technical names and technical verbs of the domain.
2. Write one instruction in each sentence. Keep a procedural sentence to 20 words or fewer. Keep a descriptive sentence to 25 words or fewer.
3. Use the active voice and simple verb tenses. Use the imperative for instructions.
4. Write one topic in each paragraph, with a maximum of six sentences.
5. Use the same word for the same thing every time. Put each term in the glossary.

## 3. Rules for this project

6. Explain each specialist term the first time it occurs, or link it to the glossary. Examples: pHash, Hamming distance, embedding, provenance.
7. Do not put internal planning labels in `README.md` or `docs/`. These are success-criterion and requirement ids (SC-001, FR-001), spec numbers and links into `specs/`, and epic names. The labels also include lesson ids (Q12, D45, L06), task ids (T010) and user-story ids (US1). In a project that keeps epics, the word "epic" is a label too. Put ADR ids, links to ADRs and links to the API contracts in `specs/` only in the "Technical notes" section.
8. Start with the task, not the mechanism. A section heading names a task that the reader does, for example "Find the scenes in a video". Put how the code works after what it does.
9. Say what each result value means in practice. Give the usual ranges, and say what a higher or a lower value means.
10. Make each example run as written. Where possible, a test runs the examples in `README.md`. In the test that runs the examples, keep a list of the examples that no test runs. For each example in the list, give the reason.

    Model weights are the files of a trained model. A Quickstart that needs weights, a GPU or a service runs in a named test tier that does not run by default. In that case, the hermetic tier parses the Quickstart commands with the real CLI. The hermetic tier is the tests that need no network, no GPU and no service. `beacon docs verify` runs each Python code block that has the marker `# beacon:test`.
11. Put history in `CHANGELOG.md` and `specs/`, not in `README.md` or `AGENTS.md`.
12. A topic that applies to all the tasks, for example errors or provenance, is a task section too. Give it a task name, for example "Handle errors".

## 4. Structure of `README.md`

1. **What is this**: after the title, one paragraph that says what the package or tool does and for whom.
2. **What you can do**: a table with three columns: the task, one line of code or one command, and a link to the section. A row can name a command of another tool, for example `pg_dump`, when the package has no command for the task. A row for a task with no command can name the file to edit, for example "Add `atoms/<family>.toml`".
3. **Install**.
4. **Quickstart**: one complete example from start to end that a new user runs first.
5. One section for each task: a short example, then what the result means.
6. **Limits**: what it does not do, or does badly.
7. **Technical notes**: build, versions, platform notes, and links to ADRs and API contracts.
8. **Develop**: for contributors. Use `CONTRIBUTING.md` if this section is long.
9. **Glossary**.

Use these fixed names for the level-2 headings, in this order. Put the task sections between "Quickstart" and "Limits". `beacon docs check` and the doctor check `writing` require these exact names. The doctor check `readme-completeness` also looks for "What is this", "Install" and "Quickstart".

## 5. Structure of `AGENTS.md`

1. **What this repository is**: two or three sentences, and its position among the related repositories.
2. **Commands**: the exact commands to set up, to run the quality gates and the tests, and to release. Name the test tiers and their markers. Each repository has its own names.
3. **Rules**: the rules that must hold, each with a link to its constitution article. Examples: the TDD pairs, the commit hook, what an agent must never do.
4. **Where things are**: a map of the directories.
5. **Current work**: a link to the active spec and plan. Do not write a history log.
6. **Known problems**: the problems that a new agent meets, each with its fix.

## 6. How the standard is enforced

- **Constitution.** An article "Documentation for people and for agents" refers to `docs/WRITING.md`. Then the Constitution Check of each plan includes the documentation.
- **Definition of done.** A change to behaviour that a user can see also changes `README.md` or `docs/`, in the same pull request. A new or changed artefact obeys section 7.
- **Check.** `beacon docs check` does the mechanical part of the standard. `beacon doctor` runs the same check as `writing`, so `beacon doctor --strict` fails on a finding. A test of the project can also run the check, so that a finding fails the test suite. The check exits with 0 when it finds nothing, 1 on a finding and 2 on a wrong option.

  The check finds sentences of more than 25 words outside code blocks. In a table, it checks each body cell as a separate text, but not the header row or a cell of code only. It uses the 25-word limit for all sentences, because it cannot find the difference between a procedural sentence and a descriptive sentence. Review checks the 20-word limit.

  The check also finds internal planning labels in `README.md` and `docs/`, but not in this file, because this file names them. The epic names are the file names in `project-management/Roadmap/epics/` and its `archive/`. An epic name with a hyphen is a label in all places. A one-word epic name, for example "curation", is also a normal English word. Because of this, the check finds a one-word epic name only before the word "epic", for example "the curation epic". When the directory `project-management/Roadmap/epics/` exists, the word "epic" is a label too, in all places.

  The label rule does not apply in a fenced code block with the info string `console`, `text` or `output`. Such a block shows real program output, and that output can show a label.

  The check makes sure that the root `README.md` has the headings of section 4 that have fixed names, in that order. These headings are "What is this", "What you can do", "Install", "Quickstart", "Limits", "Technical notes", "Develop" and "Glossary". Without `--file` or `--text`, `beacon docs check` also reports a missing `README.md` or `AGENTS.md`.

  With `--file PATH`, the check reads a file, or all the `*.md` files in a directory and in its subdirectories. To convert the pages of a repository in stages, give each page that you did not convert to `--exclude`. The test that runs the check keeps the list of excluded pages, with the reason for each page. Remove a page from that list when you convert it, and do not add a page to it. An excluded path that does not exist is an error, so the check finds an exclusion that is not correct any more.

  `beacon docs check --text` checks plain text for the sentence length and for planning labels. In each repository that has a command, a test gives it the help text of each command and each option. Give each help text alone, not the formatted page of `--help`, because its columns are not sentences. With `--null`, a NUL character separates the records of the input. The first line of each record is its source name, for example `tool fetch --help`.

  The check cannot read the STE dictionary, so review checks the words.

- **Review.** The `beacon-docs` skill is the procedure to write or update documentation. The `beacon-docs-reviewer` agent reviews each documentation change in a new context, before the pull request. It compares each fact with the code, the command help and the tests. It gives all its findings in one pass. The writer compares each finding with the code, and applies it or rejects it with a reason. Then one last review checks only the fixes ("fixes only"). Do not run more passes.

  A pass can stop before it is complete, for example because of a full disk or a limit of a tool. Then the writer records the part that the pass did not check. When the cause is not there any more, the writer runs that part again.

## 7. Project artefacts

The artefacts are the ADRs, the epics, the specs, the plans, the tasks and the constitution. The team and the agents read them to plan and build the work.

13. Use the writing rules in section 2. Rule 7 does not apply, because the artefacts are where the planning labels live.
14. Write a label with its meaning the first time it occurs in a file. Example: "`SC-nnn` (the export finishes in 5 seconds)".
15. ADR: state the decision in the first sentence of "Decision". Write the context as facts. Give each alternative that you did not choose, and the reason.
16. Epic: write each success criterion as one measurable result. Write each non-goal as one sentence.
17. Spec: write each requirement as one sentence with one "MUST". Write each acceptance scenario as Given, When and Then, with one clause in each part. Give each success criterion a number that a test can measure.
18. Plan and tasks: write each task as one imperative sentence that names the file it changes.
19. Constitution: write each article as rules with "MUST" or "MUST NOT". Give the reason for each rule in one sentence.
20. Do not rewrite an accepted ADR to obey this standard, because an accepted ADR does not change. The standard applies to each new ADR and to each new version of the other artefacts.

`beacon doctor` checks the sentence length in the ADRs, the epics, `spec.md`, `plan.md` and the constitution that change on the current branch. Review checks the other rules.

## Versions

- **Version 3** makes BEACON the only source of the standard and of its check. It adds the changes of version 1.3 of the curu standard. The `--help` text is in scope, and rule 7 gives the full list of labels. Rule 10 adds the list of examples that no test runs, and rule 12 is new. The README has the "What is this" and "Quickstart" headings, and `AGENTS.md` names the test tiers. The check reads each table cell, the README headings and plain text. The review has one full pass and one pass for the fixes. The rules of section 7 now have the numbers 13 to 20.
- **Version 2** adds section 7, so the writing rules also apply to the project artefacts. It names `beacon docs check` as the check.
- **Version 1** is the first standard. It applies to `README.md`, `docs/` and `AGENTS.md`.
