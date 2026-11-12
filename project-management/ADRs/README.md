# Architectural Decision Records

Decisions that are **hard to reverse**, involve a **real tradeoff**, or would **confuse a future contributor** without context belong here.

## Format

Use [MADR](https://adr.github.io/madr/) — see `ADR-000-template.md`.

## Numbering

`ADR-NNN-short-noun-phrase.md` — sequential, never reuse a number.
Superseded ADRs keep their file; update their status to `Superseded by ADR-###`.

## When to Write an ADR

| Situation | Write ADR? |
|-----------|-----------|
| Choosing a database or storage layer | ✅ Yes |
| Choosing between two library approaches | ✅ Yes |
| Defining an API contract or schema | ✅ Yes |
| Adding a dependency | ✅ If non-trivial |
| Fixing a bug with one obvious fix | ❌ No |
| Renaming a variable | ❌ No |
| Adding a feature that follows existing patterns | ❌ No — spec is enough |

## Index

<!-- Add a row per ADR as you create it: copy ADR-000-template.md to
     ADR-NNN-short-noun-phrase.md, fill it in, then link it here. -->

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-000](ADR-000-template.md) | Template | — | — |
| [ADR-008](ADR-008-multimodal-image-input-across-llmprovider-boundary.md) | Multimodal image input across the LLMProvider boundary | Proposed | 2026-07-22 |
| [ADR-011](ADR-011-pydantic-ai-agent-harness-with-native-ollama-model.md) | pydantic-ai Agent harness behind LLMProvider, with a native-/api/chat Ollama model | Proposed | 2026-11-12 |
| [ADR-012](ADR-012-agent-skills-as-on-demand-know-how-distinct-from-tools.md) | Agent skills as on-demand, text-only know-how, distinct from tools | Proposed | 2026-11-12 |
