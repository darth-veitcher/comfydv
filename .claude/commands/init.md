---
description: Start a new BEACON project — runs the SEED phase interactively, produces a filled problem statement, then bridges to /speckit-specify
argument-hint: [optional: brief description of what you're thinking of building]
allowed-tools: Read, Write, Bash, TodoWrite
---

You are running the BEACON SEED phase for this project.

# /init — BEACON Project Initialisation

Your goal: guide the user through the five SEED questions, then write a filled `project-management/Background/00-problem-statement.md` that they have approved.

---

## Step 0: Preflight checks

Run these silently before saying anything to the user:

```bash
# Check git hooks are installed
[ -f ".git/hooks/commit-msg" ] && echo "hooks_ok" || echo "hooks_missing"

# Check .env exists
[ -f ".env" ] && echo "env_ok" || echo "env_missing"
```

Read the current problem statement:

```bash
cat project-management/Background/00-problem-statement.md
```

Then:

- If hooks are missing: tell the user **before** anything else — `⚠️ Run ./scripts/setup.sh first to install git hooks, link agents, and create your .env. Then re-run /init.`
- If `.env` is missing: note it — `⚠️ .env not found — run ./scripts/setup.sh to create it, then fill in your Azure credentials.`
- If the problem statement already has real content (no `[Replace with` placeholders): summarise what's already there, tell the user SEED may already be done, and ask if they want to refine it or proceed straight to DESIGN with `/speckit-specify`.
- If `$ARGUMENTS` was provided: use it to pre-populate context when asking the five questions. Don't skip the questions — use the argument as a starting point to dig into.

---

## Step 1: Welcome

Say this (do not skip — it sets the mindset):

---

👋 Welcome. Before writing any code, we need to complete the **SEED phase**.

SEED answers one question: **does this problem deserve to be solved, and are we solving the right one?**

Building the wrong thing confidently is worse than building nothing. SEED exists to prevent that.

I'll ask you five questions. Your answers become `project-management/Background/00-problem-statement.md` — the document that everything else builds on.

---

## Step 2: The five SEED questions

Ask these **one at a time**. Wait for a genuine answer before moving to the next. Push back on vague answers — your job is to help them be precise, not to accept whatever they say.

### Question 1 — The problem

Ask: *"What specific problem are you solving? One sentence — not a category, not a theme. A specific, painful problem for a specific person."*

**Push back if the answer is:**
- Vague: "improve developer productivity" → ask: *"Who specifically? What does 'improve' mean in practice? What are they doing today that's painful?"*
- A solution: "I want to build X" → ask: *"That's what you want to build. What problem does it solve for who? What happens today without it?"*
- Too broad: "make things faster" → ask: *"Faster for whom, in what workflow, by how much?"*

Don't move on until the answer is specific enough that you could test whether the solution fixed it.

### Question 2 — The user

Ask: *"Who has this problem? Name the specific role and context — not 'users in general'. What do they do today as a workaround, and why does that fall short?"*

**Push back if the answer is:**
- Generic: "developers" → *"Which developers? In what context? On what team?"*
- No workaround mentioned → *"What do they do today instead? Why is that insufficient?"*

### Question 3 — Alternatives already considered

Ask: *"What three existing solutions have you already looked at? For each: why is it insufficient for this user and this problem?"*

**Push back if the answer is:**
- "I couldn't find anything" → almost never true; prompt: *"Did you look at [X, Y, Z — suggest plausible alternatives based on the domain]?"*
- Only one alternative → *"That's one. What else? What about [suggest another]?"*
- Dismissive: "they're all too complex/expensive/slow" → *"Can you be specific? What exactly makes each one insufficient?"*

**Why this matters:** if you haven't looked at what already exists, you risk building something that already exists, or something inferior to what exists.

### Question 4 — Non-goals

Ask: *"What are you explicitly NOT building? Name three things that are out of scope."*

**Why this matters:** non-goals prevent scope creep before it starts. If something isn't named as out of scope, it becomes fair game later.

**Push back if the answer is vague or thin** → *"What features might people ask for that you're deliberately not building? What would make this project ten times harder but isn't essential?"*

### Question 5 — Success criteria

Ask: *"How will you know this is working? Give me three measurable outcomes — not 'users are happy', but specific and testable."*

**Push back if the answer is:**
- Not measurable: "users find it useful" → *"How will you measure that? What does a user doing in practice tell you it worked?"*
- Too vague: "it's faster" → *"Faster by how much? p50 latency? Time-to-complete a specific workflow?"*
- Only one criterion → *"That's one. What else would tell you this was a success?"*

---

## Step 3: Pragmatic check

Before writing anything, ask the user directly:

*"Three quick honest questions:*
*1. Does this problem deserve to be solved at all — or is there a simpler workaround that's good enough?*
*2. Does it have to be done this way — or is there a non-code solution?*
*3. Does it have to be done by you — or does something already exist that could be adopted?"*

If any of these raise real doubt, say so clearly: *"I want to flag this because [reason]. Does that change how you're thinking about this?"*

Do not just fill in the template to move forward if the pragmatic check surfaces a genuine concern. Surface it and let the user decide with full information.

---

## Step 4: Draft and approval

Once all five questions have been answered and the pragmatic check is done:

1. **Write a draft** of the complete problem statement in your response — fill in every section with the user's actual answers, not placeholders.
2. **Use ExitPlanMode** to present it for review.
3. Ask: *"Does this accurately capture what we discussed? Any corrections before I write the file?"*
4. On approval, write the file:

Write the full content to `project-management/Background/00-problem-statement.md`, replacing all placeholder text with the real content from the conversation. Set both dates to today's date.

The file must have **no** placeholder text remaining — no `[Replace with`, no `YYYY-MM-DD`, no `[Outcome 1`, no `NOT [scope limit`.

---

## Step 5: Bridge to DESIGN

After writing the file, say:

---

✅ **SEED phase complete.** `project-management/Background/00-problem-statement.md` is filled in and committed.

**Next step — DESIGN:** turn this problem into a spec with GitHub Spec Kit.

```
/speckit-specify "[brief description of the first feature]"
```

Then continue with `/speckit-plan` → `/speckit-tasks`. This produces `specs/[feature]/`:
- `spec.md` — the feature specification with testable acceptance criteria
- `plan.md` — architecture, components, diagrams
- `tasks.md` — tracer bullet breakdown

(In Claude Code these are skills: `speckit-specify`, `speckit-plan`, `speckit-tasks`.)

Or, if you want to check the strategic landscape first (build vs buy decision?):
```
/design:wardley [topic]
```

---

Create a TodoWrite entry: `SEED complete — run /speckit-specify to start DESIGN`.

---

## Constraints

- **Never** accept vague answers and move on. The problem statement is the foundation — if it is weak, everything built on it is wrong.
- **Never** skip the pragmatic check. It is not a formality.
- **Never** write the file with placeholder text still in it.
- The five questions may generate a conversation that takes several exchanges. That is correct — don't rush to the template.
- If the user provides `$ARGUMENTS`, use it to orient the conversation, not to skip questions.
