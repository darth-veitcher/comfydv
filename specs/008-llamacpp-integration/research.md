# Research: llama.cpp Model Integration

## Decision: exact router-mode API shape (verified against `ggml-org/llama.cpp`'s live `tools/server/README.md`, not assumed)

llama.cpp's router mode postdates this session's training data — verified live
against the authoritative source rather than guessed, since getting field
names wrong here would silently produce broken code (wrong key = `KeyError`
or silent `None`, not an obvious failure).

**`GET /models`** response:

```json
{
  "data": [
    {
      "id": "ggml-org/gemma-3-4b-it-GGUF:Q4_K_M",
      "path": "/Users/.../gemma-3-4b-it-Q4_K_M.gguf",
      "status": {
        "value": "loaded",
        "args": ["llama-server", "-ctx", "4096"]
      },
      "architecture": {
        "input_modalities": ["text", "image"],
        "output_modalities": ["text"]
      }
    }
  ]
}
```

**Two details that would have been wrong by assumption:**

1. The model identifier field is **`id`**, not `name` — different from Ollama's
   `/api/tags`, which uses `name`. `OllamaProvider.list_models()` maps
   `m["name"]`; `LlamaCppProvider.list_models()` must map `m["id"]` instead.
2. **`status` is a nested object** (`{"value": "loaded", ...}`), not a flat
   string field. `LlamaCppProvider.list_models()` must read
   `m["status"]["value"]`, not `m["status"]` directly. A `"failed"` state
   also exists (`{"failed": true, "exit_code": ...}`) outside the five
   `ModelStatus` values the protocol defines — not handled by this feature
   (see Non-goals/edge cases in `spec.md`); a failed model is reported as
   whatever `status.value` degrades to rather than added as a sixth enum
   value, keeping `ModelStatus` unchanged across both providers.

**`POST /models/load`** and **`POST /models/unload`**: identical request
shape, `{"model": "<id>"}` (using the same `id` string from `GET /models`,
despite the request field being named `model` not `id`). Response:
`{"success": true}`.

**CLI**: `--models-dir <path>` or `--models-preset <path>.ini` — a deployment
prerequisite (spec.md Assumptions), not something comfydv configures.

## Decision: `chat_structured()` needs zero new code

`llama-server`'s `/v1/chat/completions` is OpenAI-compatible (the same
assumption ADR-007 made when adopting `pydantic-ai`). `LlamaCppProvider.chat_structured()`
calls the exact same `comfydv._llm.chat.chat_structured()` helper
`OllamaProvider` already uses, with `base_url=f"{self.host}/v1"` — the only
per-provider difference. This is the concrete proof the shared mechanism
generalizes (spec.md User Story 2/FR-004), not just an assumption.

## Decision: `chat()` (non-structured) also reuses the OpenAI-compatible endpoint

Unlike Ollama (which has both a native `/api/chat` and an OpenAI-compat
`/v1/chat/completions`), llama-server's primary chat endpoint is the
OpenAI-compatible one. `LlamaCppProvider.chat()` POSTs to
`{host}/v1/chat/completions` (via the existing `_post_json` helper, no new
HTTP client) rather than mirroring Ollama's native-endpoint choice — the
response shape (`choices[0].message.content`) differs from Ollama's native
`message.content` and must be parsed accordingly.

## Decision: no protocol changes needed

`LLMProvider`'s five methods (`list_models`/`load_model`/`unload_model`/
`chat`/`chat_structured`) already cover everything router mode needs — this
was the actual point of designing the protocol at the operation level in
ADR-007, and this research confirms it held up against llama.cpp's real API,
not just Ollama's.
