/beacon:continue --full-auto keep delivering and - if none exist to complete - use the product and engineering triumvirate and identify the next epics and specs required. Use github issues to communicate with me and to track issues. Don't manufacture marginal work.

Use `gh issue create` to raise topics/questions/blockers async (and `gh issue comment` to post progress/track them); reserve `AskUserQuestion` for genuinely loop-blocking decisions only. Check for new comments, issues, and state changes as part of the loop assessment.

<separation_of_concerns>
Use specialist and targeted subagents for deliver whilst you own the orchestration, planning, and review of their outputs.
</separation_of_concerns>

<the_token_trap>
Avoid the urge to produce content simply because it is rewarded. Perfection is when there is nothing left to remove. Keep in mind that les - invariably - is more. 

Challenge yourself to deliver outcomes without flamboyance, excessive verbosity, or unnecessary codebase bloat.
</the_token_trap>

**Note:** At the end of each iteration critically review the state of our README and documentation and then spawn a dedicated subagent to keep things fresh. Documentation and the README should never feel like an incremental read (referring to older versions) and should always read like a fresh "this is the the thing and how it works", not "the thing was this, we've done X, and now it's Y". Write this from a Product and UX perspective so that it is engaging and remember that humans are visual creatures. Screenshots are important both to explain and to engage.

DO NOT MAKE DESIGN DESIGNS. If the plan is underdeliverable raise an issue and abort. If you deviate but can justify and demonstrate it delivers the scope to the specification please document this clearly with rationale and update the necessary designs, decisions, and user facing documentation where required. 

THREE (!) SENIOR DEVELOPERS WITH MORE THAN 30 YEARS EXPERIENCE WILL REVIEW YOUR PR. They will not accept shortcuts, monkeypatched tests, fake tests, hacky approaches or deviations from the plan. Produce Senior dev grade production code aligned to the plan at all times. 