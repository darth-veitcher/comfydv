# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- BEACON framework bootstrap: problem statement, constitution, roadmap, architecture document
- `CHANGELOG.md` (this file)
- README: What-is-this, Install, and Quickstart sections
- `LLMProvider` protocol (`comfydv._llm`) — a shared adapter boundary so ComfyUI LLM nodes work with any backend that implements it, starting with `OllamaProvider`. Structured output now goes through `pydantic-ai` (ADR-007), superseding the hand-rolled Ollama tool-calling approach.
- **Chat Completion** now accepts an optional `image` input for vision-capable models (VLMs): wire a ComfyUI `IMAGE` and the connected model can describe or reason about it. Works identically on both backends (Ollama multimodal models; llama.cpp launched with `--mmproj`), and composes with structured output and multi-turn history. Images are carried on `Message.images` and translated to each backend's native shape (Ollama's flat `images` array, llama.cpp's OpenAI `image_url` parts, pydantic-ai `BinaryContent` on the structured path) — ADR-008, extending ADR-007's adapter pattern to a second input modality. Text-only workflows are unchanged when no image is wired.
- **Ollama Option — Disable Thinking** node: turn off (or explicitly re-enable) a "thinking"-capable model's chain-of-thought reasoning. Chains into the same composable `OLLAMA_OPTIONS` socket every other `OllamaOption*` node uses, but works for both backends — each `LLMProvider` implementation pops the `think` key back out and translates it to its own wire shape (Ollama: a top-level `think` field; llama.cpp: `chat_template_kwargs`/`reasoning_effort` request-body fields, not live-verified — see ADR-010).

### Changed
- **Breaking:** `OllamaChatCompletion` → `ChatCompletion`, `OllamaModelSelector` → `LLMModelSelector`, `OllamaLoadModel` → `LLMLoadModel`, `OllamaUnloadModel` → `LLMUnloadModel`, and the `OLLAMA_CLIENT` socket type → `LLM_CLIENT` — these nodes are now backend-generic. `OllamaClient` is unchanged by name but now outputs an `OllamaProvider` rather than a plain string; existing saved workflows using the old node/socket names need reconnecting (see `comfydv.ollama.MIGRATION_MAP` for the full old→new mapping).
- `ChatCompletion`'s `structured_output=True` path now routes Ollama through Ollama's native `/api/chat` + `"format"` instead of the shared `pydantic-ai` OpenAI-compat path — Ollama's OpenAI-compatible endpoint was found to silently reload the model at its default context size on every call, discarding any `options` (e.g. `num_ctx`) override. `LlamaCppProvider` is unaffected and keeps the shared path, switched to `pydantic-ai`'s `NativeOutput` mode (ADR-009).

### Fixed
- `structured_output=True` requests could fail validation ("token limit exceeded before any response was generated") against "thinking"-capable models, which spent their whole token budget on chain-of-thought reasoning before ever producing the structured response (ADR-009).
- A non-required structured-output schema field rejected an explicit `null` value from the model (only an *omitted* field was tolerated), even though models routinely emit explicit `null` for absent optional fields.

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
