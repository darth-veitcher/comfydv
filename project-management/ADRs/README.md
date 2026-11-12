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
| [ADR-001](ADR-001-stdlib-logging-over-console-libraries.md) | Use stdlib logging instead of colored console output libraries | Accepted | 2026-06-28 |
| [ADR-002](ADR-002-nullhandler-pattern-for-library-loggers.md) | NullHandler pattern for the comfydv package root logger | Accepted | 2026-06-28 |
| [ADR-003](ADR-003-requirements-txt-authoring-policy.md) | Hand-authored requirements.txt as a curated subset of pyproject.toml | Accepted | 2026-06-28 |
| [ADR-004](ADR-004-aiohttp-over-httpx-for-ollama.md) | Use aiohttp for Ollama HTTP communication instead of httpx | Accepted | 2026-06-28 |
| [ADR-005](ADR-005-ollama-host-config-via-client-node.md) | Ollama host configuration via OllamaClient node and OLLAMA_CLIENT socket type | Accepted | 2026-06-28 |
| [ADR-006](ADR-006-structured-ollama-output-tool-calling-not-pydantic-ai.md) | Structured Ollama output via OpenAI-compatible tool-calling + dynamic pydantic validation, not pydantic-ai | Superseded by [ADR-007](ADR-007-llm-provider-adapter-pattern.md) | 2026-07-09 |
| [ADR-007](ADR-007-llm-provider-adapter-pattern.md) | LLMProvider adapter pattern shared across Ollama and llama.cpp | Accepted | 2026-07-11 |
| [ADR-008](ADR-008-multimodal-image-input-across-llmprovider-boundary.md) | Multimodal image input carried on the Message across the LLMProvider boundary | Accepted | 2026-07-22 |
| [ADR-009](ADR-009-native-structured-output-mode.md) | Provider-specific structured output — NativeOutput for llama.cpp, hand-rolled native `/api/chat` for Ollama | Accepted | 2026-07-25 |
| [ADR-010](ADR-010-disable-thinking-toggle.md) | `"think"` as an options-carried, per-provider-translated toggle | Accepted | 2026-07-25 |
| [ADR-011](ADR-011-pydantic-ai-agent-harness-with-native-ollama-model.md) | pydantic-ai Agent harness behind `LLMProvider`, with a native-`/api/chat` Ollama model | Accepted | 2026-11-12 |
| [ADR-012](ADR-012-agent-skills-as-on-demand-know-how-distinct-from-tools.md) | Agent skills as on-demand know-how, distinct from tools | Accepted | 2026-11-12 |
| [ADR-013](ADR-013-monty-sandbox-code-mode-and-skill-scripts.md) | Monty sandbox for code mode and skill scripts, with no authority of its own | Accepted | 2026-11-12 |
| [ADR-014](ADR-014-telemetry-off-by-default.md) | Telemetry and phone-home behaviour off by default | Accepted | 2026-11-12 |
| [ADR-015](ADR-015-mcp-server-trust-model.md) | MCP server trust model: layered config, free toggles, approve on first use | Accepted | 2026-11-12 |
| [ADR-016](ADR-016-constitution-1-1-documentation-article.md) | Constitution 1.1.0: add the documentation article | Accepted | 2026-11-12 |
| [ADR-017](ADR-017-release-channels-and-pipeline.md) | Release channels and pipeline: PSR on gitflow, PyPI pre-releases, Registry stable only | Accepted | 2026-11-12 |
