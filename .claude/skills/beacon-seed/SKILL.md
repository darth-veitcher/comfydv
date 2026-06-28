---
name: beacon-seed
description: BEACON SEED phase — evaluate whether a new idea deserves to exist before any code is written. Use when a user opens with "I have an idea for…", "Should I build…", or any new-project trigger.
---

# Phase 1: SEED — Does this idea deserve to exist?

**Purpose:** Evaluate a new idea rigorously before committing to building it.

**Entry triggers:** "I have an idea for…" / "Should I build…" / new project start

---

## The SEED Questions

Answer these honestly before writing any code:

### 1. What specific problem are you solving?

One sentence. Not a category, not a theme — a specific, painful problem for a specific person.

> Bad: "Improve developer productivity"
> Good: "Data analysts waste 2 hours/day querying Fabric semantic models manually when they could describe what they want in plain English"

### 2. Who has this problem?

Name them specifically. What is their role, context, and current workaround?

### 3. What are three existing solutions?

Before building, find what already exists. Why is each insufficient?

1. **[Solution A]** — why it fails: …
2. **[Solution B]** — why it fails: …
3. **[Solution C]** — why it fails: …

### 4. Is your solution 10x simpler than the alternatives?

If not, reconsider. Building something marginally better than an existing tool is rarely worth it.

### 5. What are you explicitly NOT building?

Non-goals prevent scope creep. Name them now.

---

## SEED Deliverable

Create `project-management/Background/00-problem-statement.md` using the template.

A SEED phase is complete when:
- [ ] One specific problem is named
- [ ] One specific user is named
- [ ] Success criteria are measurable
- [ ] Non-goals are explicit
- [ ] At least three alternatives have been considered and rejected

Run `beacon doctor` after writing the problem statement — it will catch placeholder text that survived edits.

**Do not proceed to DESIGN until these are answered.**

---

## Pragmatic check

Ask: "Does this problem deserve to be solved *at all*? Does it have to be done this way? Does it have to be done by me?"

If the answer to any of these is uncertain, explore more before committing.
