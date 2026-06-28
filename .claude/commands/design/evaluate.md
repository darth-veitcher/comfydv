---
description: Structured technology evaluation — scored build-vs-buy comparison that produces an ADR-ready recommendation
argument-hint: [technology decision or component to evaluate]
allowed-tools: Read, Write, Grep, Glob
---

Evaluate technology options for: $ARGUMENTS

# Technology Evaluation — Build vs. Buy Analysis

Use this command when a DESIGN decision requires choosing between building a component, using an
open-source library, buying a SaaS product, or using a cloud service. The output feeds directly
into an ADR.

## When to use this command

- During **DESIGN** when an architectural option involves a significant technology choice
- When the spec design phase surfaces a "which database / queue / search engine / auth provider?"
  question that deserves a structured answer
- When `/design:wardley` identifies a component as Product/Commodity and you need to pick the
  right product

---

## Step 1: Define the decision

State clearly:
- **What capability is needed?** (one sentence, functional)
- **What are the non-negotiables?** (hard requirements that eliminate options immediately)
- **What is the context?** (team size, scale, budget constraints, existing stack)

---

## Step 2: Identify options

Generate at least three options. Always include:
1. **Build in-house** (greenfield custom implementation)
2. **Open-source library/framework** (integrate existing OSS)
3. **Managed service / SaaS** (vendor-hosted, pay-to-use)

Add further options if they are genuinely distinct.

---

## Step 3: Score each option

Rate each option 1–5 on each criterion. Adjust the weight column to reflect project priorities
(weights must sum to 100).

| Criterion | Weight | Build | OSS | SaaS | [Other] |
|-----------|--------|-------|-----|------|---------|
| **Fit to requirements** — does it meet the functional spec? | 25 | | | | |
| **Operational complexity** — how hard to run, monitor, upgrade? | 20 | | | | |
| **Time to value** — how quickly can the team deliver with this? | 15 | | | | |
| **Cost (TCO 2 yr)** — licensing + infra + engineering time | 15 | | | | |
| **Vendor/community risk** — abandonment, lock-in, support quality | 10 | | | | |
| **Security & compliance** — data residency, audit, vulnerability cadence | 10 | | | | |
| **Team capability** — does the team have skills or can acquire them quickly? | 5 | | | | |
| **TOTAL (weighted)** | 100 | | | | |

Scoring guide:
- **5** — Excellent fit; no significant concern
- **4** — Good fit; minor concerns
- **3** — Adequate; notable trade-offs
- **2** — Poor fit; significant concerns
- **1** — Unacceptable; eliminates or blocks a requirement

---

## Step 4: Identify deal-breakers

Before accepting the top scorer, explicitly check:

- Does any option violate a **hard requirement** (compliance, latency, data sovereignty)?
- Is the leading option in a zone where it should be **commoditised** (per Wardley stage)? If so,
  the Build option is probably waste.
- Does the team have **genuine expertise** to build and operate this, or is that an optimistic
  assumption?

---

## Step 5: Produce the output

Save as `project-management/Work/analysis/evaluate-[topic].md`:

```markdown
# Technology Evaluation: [Topic]

## Decision
[One sentence: what capability are we choosing a technology for?]

## Context
- Team: [size, skills]
- Scale: [expected load]
- Constraints: [budget, compliance, existing stack]

## Non-Negotiables
- [Hard requirement 1]
- [Hard requirement 2]

## Options Evaluated

### Option 1: Build in-house
**Summary:** [Brief description]
**Pros:** [Key strengths]
**Cons:** [Key weaknesses]

### Option 2: [OSS library/framework name]
**Summary:** [Brief description]
**Pros:** [Key strengths]
**Cons:** [Key weaknesses]

### Option 3: [SaaS/managed service name]
**Summary:** [Brief description]
**Pros:** [Key strengths]
**Cons:** [Key weaknesses]

## Scoring

| Criterion | Weight | Build | [OSS] | [SaaS] |
|-----------|--------|-------|-------|--------|
| Fit to requirements | 25 | | | |
| Operational complexity | 20 | | | |
| Time to value | 15 | | | |
| Cost (TCO 2 yr) | 15 | | | |
| Vendor/community risk | 10 | | | |
| Security & compliance | 10 | | | |
| Team capability | 5 | | | |
| **TOTAL** | 100 | | | |

## Deal-Breaker Check
- [ ] No hard requirements violated by recommended option
- [ ] Wardley stage checked — not building in commodity zone
- [ ] Team capability assessment is honest, not optimistic

## Recommendation

**Recommended option:** [name]
**Rationale:** [2–3 sentences explaining why this option wins]
**Key risk to monitor:** [the main risk of this choice and how to detect if it becomes a problem]

## Next Step

Create ADR-NNN: [topic] using this analysis as the "Considered Alternatives" section.
```

---

## Guidelines

- Do not recommend "build" for components that are clearly Product or Commodity (use
  `/design:wardley` first if unsure)
- Be honest about TCO — "free" open-source is not free to operate
- If two options are within 10 points of each other on the score, prefer the option with lower
  operational complexity (teams consistently underestimate ops burden)
- The evaluation is an input to the ADR, not a replacement for it
