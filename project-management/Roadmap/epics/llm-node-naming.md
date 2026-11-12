# Epic: LLM Node Naming (clean break)

<!-- Write this epic to section 7 of docs/WRITING.md (ASD-STE100). -->

## Status
Planning  — started 2026-11-12

## Why now
Fourteen LLM nodes and three socket types have "Ollama" in their names. But they
operate with both backends, Ollama and llama.cpp. The agent harness adds more
nodes. Rename now, before more nodes use the old names.

The maintainer chose a clean break: no deprecated aliases. A clean break is
correct only if the release documents it, so this epic comes after
`release-pipeline`.

## Specs
_SpecKit specs that contribute to this epic. `beacon specify --epic <slug>`
links them. Otherwise, add each one by hand after you run `/speckit-specify`._

<!-- - specs/011-llm-node-naming/   — rename, module split, migration notes -->

## ADRs
- The epic records the clean-break decision (2026-11-12). The spec writes it as an ADR.
- [ADR-007](../../ADRs/ADR-007-llm-provider-adapter-pattern.md) — the first rename used `MIGRATION_MAP`.

## Success criteria
- Only `OllamaClient` and `LlamaCppClient` have a backend in their names.
- Node keys, display names and categories use the `dv/llm/...` tree.
- Socket types are `LLM_OPTIONS`, `LLM_HISTORY` and `LLM_HEADERS`.
- `src/comfydv/ollama.py` is split into modules by role.
- `MIGRATION_MAP` contains each old name and each new name.
- `CHANGELOG.md` has a **Breaking** section. `README.md` has the migration table.
- `workflows/ltx-i2v-pipeline.json` uses the new names and loads.
- Each LLM node input has a tooltip.

## Non-goals
- Deprecated aliases for the old names.
- Changes to node behaviour.

## Notes
Optional: a `scripts/migrate_workflow.py` that applies `MIGRATION_MAP` to a saved
workflow file.

Design detail: `project-management/Work/analysis/llm-agent-harness.md` §5.
