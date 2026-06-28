---
description: Inferential SEED-phase scaffold — has a conversation with the user, infers the template fields, presents them back for confirmation, then applies. Plan-mode style.
argument-hint: (no arguments — operates on the current project)
allowed-tools: Bash, Read, Edit, Glob, Grep
---

You're helping the user fill in BEACON's SEED-phase templates. The user invoked this command because the CLI's `beacon seed scaffold` is too literal — they want a conversation, not a form.

## Files in scope

- `project-management/Background/00-problem-statement.md` — the gate. Has placeholder tokens like `[Replace with your problem statement]`, `[Specific person, role, or team — not "users in general"]`, `[When and where they encounter this problem]`, `[What they do today and why it falls short]`, `[Outcome 1 — e.g. "..."]`, `[Outcome 2]`, `[Outcome 3]`, `[scope limit 1/2/3]`, `[One paragraph on the business or human impact...]`, `[Technical, organisational, or timeline constraints...]`.
- `project-management/Background/01-final-architecture-document.md` — has `[Project Name]` in several places (diagram titles).
- `project-management/Roadmap/README.md` — has `[Project Name]` and `[Replace with your project's vision statement.]`.

Each of those files also has `YYYY-MM-DD` markers in the footer that should be stamped with today's date.

## Conversation flow — plan-mode style

### 1. Orient (silently)

Before opening the conversation, run:

```bash
beacon seed
```

Read the three files. Note which placeholders are still in place — only ask about those. If everything's already filled in, tell the user and stop.

### 2. Open with one or two broad questions

Not a form. Start with something like:

> "Tell me about this project. What is it, who's it for, and what's broken about today?"

Listen. Take notes. If the user gives you a rich paragraph, you have most of what you need to infer. If they give a sentence, ask one tight follow-up — e.g. "And who's actually hitting that today?" or "When does that bite them?".

Optionally a second broad question for the year-ahead view:

> "Looking ahead a year — what does 'winning' look like?"

### 3. Infer the template fields

From the user's answers, draft concrete values for **every** template slot. Don't pad with filler — but DO infer. The user said this should feel like Claude in plan mode: take a position, then ask "is this right?"

Slots to infer:

| Slot | Source for inference |
|---|---|
| Project name | Direct ask if not implied; otherwise pick a codename from the user's language. |
| Core problem (one sentence) | The user's first answer, distilled to one sentence. |
| Who (target user) | The role/team/persona the user mentioned. Be specific — "platform engineers responsible for X", not "developers". |
| Context (when/where) | The moment/scenario the user described. |
| Current pain (what they do today) | Today's workaround + why it falls short. |
| Success criteria (1–3 measurable items) | Outcomes implied by the user's framing. Make them measurable — "<5s response", "<1 page error message", "new engineer self-serves on day one". |
| Non-goals (1–3) | Things the user implied are out of scope, OR adjacent things you'd guess to call out explicitly. |
| Why this matters | One sentence on the impact — what becomes possible / different. |
| Constraints | Tech/org/timeline bounds the user mentioned. If none mentioned, write "(none called out yet)". |
| Roadmap vision (paragraph) | The user's year-ahead answer, sharpened into a paragraph. |

### 4. Present the inference back

Show the user every inferred value in a clear structure (table or bullet list). Use their exact phrasing where you can; only rewrite for compression and clarity.

End with: **"Does this look right? Anything to refine before I write it in?"**

### 5. Iterate

If the user pushes back on a slot, adjust. Don't argue or over-justify. Take the correction and move on. If they say "looks good," go to step 6.

### 6. Apply

Edit the three files with the confirmed values. For each file:

- **Problem statement** (`project-management/Background/00-problem-statement.md`):
  - Replace each `[…]` placeholder with the corresponding confirmed value.
  - For Success Criteria: if 1 outcome, leave only `- [ ] <outcome 1>` and remove the `- [ ] [Outcome 2]` and `- [ ] [Outcome 3]` lines. If 2 outcomes, leave two `- [ ] <outcome>` lines. If 3+, leave three.
  - For Non-Goals: same logic — render `1. NOT <item>`, `2. NOT <item>`, … and remove unused numbered lines.
  - Stamp `YYYY-MM-DD` → today's date (both `_Created:_` and `_Last updated:_`).
- **Architecture** (`01-final-architecture-document.md`):
  - Replace every `[Project Name]` with the confirmed project name.
  - Stamp `YYYY-MM-DD` → today's date in the footer.
- **Roadmap** (`Roadmap/README.md`):
  - Replace `[Project Name]` with the project name.
  - Replace `[Replace with your project's vision statement.]` with the confirmed vision paragraph.
  - Stamp the `**Last reviewed:** YYYY-MM-DD` header (and the footer line) with today's date.

### 7. Verify

After applying, run:

```bash
beacon seed
```

The first three checks (`problem-statement`, `architecture`, `roadmap-vision`) should all be OK. `roadmap-staleness` should be OK too because you stamped the review date.

If `beacon seed` still shows FAIL or WARN, read the message — there's a placeholder you missed. Find it, fix it, run `beacon seed` again.

### 8. Fill the constitution

Check for a constitution stub:

```bash
test -f .specify/memory/constitution.md && echo "present" || echo "absent"
```

- **absent** — skip. Remind the user that `/beacon.constitution` is available once the spec workflow is initialised (`specify init && beacon upgrade`).
- **present** — the Background docs are freshly filled and are the best seed material the constitution will ever have. Continue with `/beacon.constitution` now (no extra arguments needed — it reads the Background docs you just wrote).

## Tone constraints

- **No Product-dogma jargon.** Strict ban on SAM, TAM, ICP, PMF, "North Star metric", "Jobs to be Done", "user persona archetype". BEACON's voice is practical and opinionated, not Lean Startup.
- **No filler.** If the user's answer doesn't give you enough to infer a slot, ask one tight follow-up. Don't invent.
- **Reflect the user's voice, sharpened.** Your job is to compress and clarify what they said — not to decide what they meant.
- **Concrete beats generic.** "Platform engineers responsible for data-product reliability at a mid-size SaaS" beats "users".

## After SEED is green

Tell the user:

> SEED is filled in. Next:
> - `/beacon.epics` to plan and create your initiatives, or
> - `beacon doctor` to confirm everything's green across the project.
