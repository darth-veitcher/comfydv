# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- BEACON framework bootstrap: problem statement, constitution, roadmap, architecture document
- `CHANGELOG.md` (this file)
- README: What-is-this, Install, and Quickstart sections
- `LLMProvider` protocol (`comfydv._llm`) — a shared adapter boundary so ComfyUI LLM nodes work with any backend that implements it, starting with `OllamaProvider`. Structured output now goes through `pydantic-ai` (ADR-007), superseding the hand-rolled Ollama tool-calling approach.

### Changed
- **Breaking:** `OllamaChatCompletion` → `ChatCompletion`, `OllamaModelSelector` → `LLMModelSelector`, `OllamaLoadModel` → `LLMLoadModel`, `OllamaUnloadModel` → `LLMUnloadModel`, and the `OLLAMA_CLIENT` socket type → `LLM_CLIENT` — these nodes are now backend-generic. `OllamaClient` is unchanged by name but now outputs an `OllamaProvider` rather than a plain string; existing saved workflows using the old node/socket names need reconnecting (see `comfydv.ollama.MIGRATION_MAP` for the full old→new mapping).

## [0.1.0] — 2026-06-01

### Added
- `FormatString` node: dynamic string formatting via Python f-strings or Jinja2 `SandboxedEnvironment`
  - Auto-detects template variables and exposes them as typed input sockets
  - Outputs fixed at positions 0 (`formatted_string`) and 1 (`saved_file_path`); variable pass-through at 2+
  - Registers aiohttp routes on ComfyUI's `PromptServer` for live widget updates from the JS layer
- `RandomChoice` node: seed-controlled selection from an arbitrary number of typed inputs
- `CircuitBreaker` node: raises `InterruptProcessingException` to halt a queue run without crashing ComfyUI
- Comprehensive pytest suite runnable without a live ComfyUI instance
- MkDocs-material documentation site at [darth-veitcher.github.io/comfydv](https://darth-veitcher.github.io/comfydv/stable/)

### Changed
- `FormatString` output order reversed so `formatted_string` and `saved_file_path` are always at fixed positions 0 and 1 (previously variable outputs came first, which broke workflow connections on re-render)
