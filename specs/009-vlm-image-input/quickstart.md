# Quickstart: Describe an image with ChatCompletion

**Spec**: [spec.md](./spec.md)

Minimal end-to-end walkthrough of the feature once shipped.

## Prerequisites

- A running backend with a **vision-capable** model:
  - **Ollama** — a multimodal model pulled and available (e.g. a llava-class model), or
  - **llama.cpp** — `llama-server` launched in router mode **with a multimodal projector**: `--mmproj <projector.gguf>` alongside the model.
- comfydv installed in ComfyUI.

## Steps

1. Add an image source to the canvas (e.g. **Load Image**) → gives an `IMAGE`.
2. Add a client node (**OllamaClient** or **LlamaCppClient**) → gives `LLM_CLIENT`.
3. Add **ChatCompletion**. Wire:
   - `client` ← the client node
   - `model` ← a vision-capable model name (typed or wired)
   - `prompt` ← `"Describe this image in one sentence."`
   - `image` ← the `IMAGE` from step 1  ← **the only new wire**
4. Queue the prompt. The `response` output is a text description of the image.

## Structured variant (optional)

- On **ChatCompletion**, set `structured_output = True` and provide a schema, e.g.:
  ```json
  {"type":"object","properties":{"caption":{"type":"string"},"has_text":{"type":"boolean"}},"required":["caption","has_text"]}
  ```
- Run: each field (`caption`, `has_text`) appears as its own typed output,
  populated from the image, with no required field blank.

## Swap backends (proves FR-004 / SC-002)

- Replace **OllamaClient** with **LlamaCppClient** (pointed at an `--mmproj`
  server) — **change nothing else**. Re-queue: same image description path.

## What stays the same

- Leave `image` un-wired and ChatCompletion behaves exactly as before — text-only,
  identical results. No existing workflow changes.

## Expected failure (proves FR-006 / SC-005)

- Wire an image but select a **non-vision** model (or a `llama-server` started
  without `--mmproj`): the node reports a clear error that the model/server
  can't process images — it does not silently answer as if no image was sent.
