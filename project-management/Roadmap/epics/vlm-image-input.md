# Epic: VLM Image Input for ChatCompletion

## Status
Planning — started 2026-07-22

## Why now

The generic `ChatCompletion` node and the `LLMProvider` protocol landed
text-only (ADR-007), which explicitly deferred any protocol change for a new
capability as "its own follow-up." Both shipped backends can already serve
vision models — Ollama multimodal models via `/api/chat`'s per-message
`images`, and llama.cpp via a multimodal projector (`mmproj`) on the same
OpenAI-compatible `/v1/chat/completions` the provider already calls — so the
gap is entirely on comfydv's client side, not the servers'. Coupling the chat
node with a VLM to describe or reason about images produced elsewhere in a
workflow is a frequently-wanted next step, and the adapter pattern makes it a
small, symmetric addition rather than a new node family.

## Specs
_SpecKit specs that contribute to this epic._

- specs/009-vlm-image-input/ — wire a ComfyUI IMAGE into the existing ChatCompletion node; images carried on the Message and translated per-provider

## ADRs
_Cross-cutting decisions this epic required._

- project-management/ADRs/ADR-008-multimodal-image-input-across-llmprovider-boundary.md — carry images as an optional `Message.images` field; each provider translates to its own wire shape (extends ADR-007's adapter pattern to a second input modality)
- project-management/ADRs/ADR-007-llm-provider-adapter-pattern.md — the adapter pattern this epic extends; the generic node/protocol it adds an image path to

## Success criteria

- `Message` carries an optional `images` field; text-only requests remain byte-for-byte unchanged (existing Ollama + llama.cpp provider tests stay green)
- `ChatCompletion` gains one **optional** `IMAGE` input — no new node classes, no new socket types; a workflow author gains vision by wiring one socket
- A wired image reaches a vision model and produces a description/answer on **both** backends:
  - Ollama: flat per-message `images` passes through `/api/chat` untransformed
  - llama.cpp: mapped to OpenAI `image_url` content parts on `/v1/chat/completions`
- Structured output with an image works via the shared `chat_structured()` (pydantic-ai multimodal content) — one implementation, both backends
- A text-only model that receives an image degrades to a clear backend error surfaced by the node, not a crash
- Test coverage mirrors the `OllamaProvider`/`LlamaCppProvider` conventions (mock at the provider's own transport seam); CI smoke test passes
- No new runtime dependencies beyond what ADR-007 already introduced

## Non-goals

- No image **output** or image generation — input-to-VLM only
- No new node classes or socket types — additive optional input on the existing generic node
- No changes to the client/config nodes (`OllamaClient`, `LlamaCppClient`) or model-management nodes
- No auto-provisioning of vision models — the user must have a multimodal model loaded (Ollama multimodal model; llama.cpp launched with an `mmproj` projector); this epic does not install or configure it
- No video, audio, or document/PDF modalities — still images only
- No image preprocessing beyond what's needed to hand a ComfyUI IMAGE tensor to a backend (no resizing policy, tiling, or OCR of our own)
- No `OllamaOption*` parameter translation work — inherited unchanged from ADR-007's scope

## Notes

Multimodal readiness is a deployment prerequisite, not something comfydv
configures: document in node tooltips that the wired model must be
vision-capable, and that llama.cpp needs `--mmproj`. The exact wire shapes
(Ollama `/api/chat` `images`, OpenAI `image_url`, pydantic-ai `BinaryContent`)
are verified live in the spec's `research.md`/`plan.md`, consistent with how
the llama.cpp epic verified router-mode endpoints.

Reference: ADR-008, ADR-007, GitHub issue #15.
