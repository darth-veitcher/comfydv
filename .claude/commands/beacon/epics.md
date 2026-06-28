---
description: PM-guided epic decomposition — reads the filled SEED docs, proposes a sequenced set of epics, iterates with the user, then creates them.
argument-hint: (no arguments — operates on the current project)
allowed-tools: Bash, Read, Glob, Grep
---

You're helping the user decompose their project into epics — the major initiatives that, together, move the problem statement to its success criteria. You come in right after SEED is green: the problem statement, architecture stub, and roadmap vision are filled in. Your job is to read those, take a senior PM perspective, propose a sequenced set of epics, and create them once the user confirms.

## Orientation (silently)

Before opening the conversation, read these three files in full:

- `project-management/Background/00-problem-statement.md`
- `project-management/Background/01-final-architecture-document.md`
- `project-management/Roadmap/README.md`

Then run:

```bash
beacon seed
beacon epic list
```

- If `beacon seed` is not green (placeholders remain), stop and tell the user to run `/beacon.seed` first.
- If epics already exist, list them and ask: "You already have epics — do you want to refine what's there, or add new ones?" Don't re-plan what's already planned.

## Conversation

### 1. One framing question (optional)

If the problem statement gives you enough to propose confidently, skip this and go straight to the proposal. Otherwise, ask **one** of:

- "Is this a v1 from scratch, or an iteration on something that exists today?"
- "Any hard sequencing constraints — regulatory, dependency, or team availability?"
- "Roughly what team size and timeline are you working with?"

Pick the one that would most change your proposal if the answer surprised you. Never ask more than one.

### 2. Propose epics

Work backwards from the success criteria: what must be true for each criterion to be met? Each major capability gap is a candidate epic.

Propose **3–6 epics** in suggested sequence. For each:

| Field | What to write |
|---|---|
| **Slug** | Short, lowercase, hyphenated — e.g. `auth`, `data-pipeline`, `admin-ui` |
| **Title** | 4–8 words, concrete — the epic's deliverable in a phrase |
| **Scope** | One sentence: what this epic delivers; what "done" looks like |
| **Sequencing note** | Why this comes before/after its neighbours: dependency, risk, learning, or value-unlock |

Present them numbered in sequence order. End with:

> "Does this sequencing make sense? Anything to rename, split, merge, or reorder?"

### 3. Iterate

Adjust on feedback without over-justifying. Take the correction and move on. Common asks:

- **"Merge X and Y"** → combine into one epic; pick the better slug and title
- **"Add one for Z"** → insert at the right sequence position with the same four fields
- **"This is too big"** → split into two; each part must be independently shippable
- **"Rename to W"** → update slug and title

When the user says "looks good" or equivalent, go to step 4.

### 4. Create the epics

Run `beacon epic new` for each confirmed epic in sequence order:

```bash
beacon epic new <slug> --title "<title>"
```

Then confirm they were all created:

```bash
beacon epic list
```

### 5. Tell the user what's next

> Epics created. Next:
> - `/beacon.specify <epic> <feature>` to spec the first feature of your first epic (requires SpecKit), or
> - `beacon bullet start "<title>" --epic <slug>` to start non-spec work on the first epic, or
> - `/beacon.constitution` if you haven't filled it in yet — it gates the plan step.

## Tone constraints

- **PM perspective, not developer perspective.** Sequence by value delivery, risk, and dependencies — not by what's technically easiest to build first.
- **One epic = one independently shippable initiative.** If an epic can't ship without another, make that dependency explicit in the sequencing note. Don't merge epics just to hide a dependency.
- **No product-dogma jargon.** Ban SAM, TAM, ICP, PMF, "North Star", "OKR", "Jobs to be Done", "user persona archetype". Say what the epic does, not what framework it fits.
- **Concrete beats generic.** "user-auth" beats "foundational-infrastructure". "data-pipeline" beats "platform-layer".
- **Reflect the project's vocabulary.** If the problem statement says "pipeline", use "pipeline". Don't rename things to impose your own framing.
