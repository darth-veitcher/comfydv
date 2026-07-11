# Data Model: llama.cpp Model Integration

No new types — this feature is a second implementation of the existing
`LLMProvider` protocol, `ModelStatus`, `ModelInfo`, and `Message` types
(`src/comfydv/_llm/provider.py`, unchanged). This file documents
`LlamaCppProvider`'s field mapping from llama-server's router-mode JSON onto
those existing types (see `research.md` for the verified API shapes).

## `LlamaCppProvider.list_models()` → `ModelInfo` mapping

| `ModelInfo` field | Source (`GET /models` response, per model in `data[]`) |
|---|---|
| `name` | `id` — **not** `name` (llama.cpp's field name differs from Ollama's) |
| `status` | `status.value` — nested object, not a flat string |
| `size` | Not provided by this endpoint; `None` |

`status.value` maps directly onto `ModelStatus`'s five values
(`unloaded`/`loading`/`loaded`/`sleeping`/`downloading`) — llama.cpp's
vocabulary is exactly `ModelStatus`'s full set, so unlike `OllamaProvider`
(which normalizes into a narrower subset), `LlamaCppProvider` needs no
approximation. A `"failed": true` state exists outside this vocabulary
(model process crashed) — out of scope per spec.md's edge cases; treated as
whatever `status.value` reports rather than added as a sixth enum value.

## `LlamaCppProvider.load_model()` / `unload_model()`

Both `POST /models/load` and `POST /models/unload` take `{"model": <id>}` —
the same `id` string `list_models()` returns as `ModelInfo.name`. No mapping
ambiguity here (unlike Ollama, where load/unload uses `/api/generate`'s
`keep_alive` side effect rather than a dedicated endpoint).

## `LlamaCppProvider.chat()` / `chat_structured()`

Both reach `llama-server`'s OpenAI-compatible `/v1/chat/completions` —
`chat_structured()` calls the existing shared `comfydv._llm.chat.chat_structured()`
helper unchanged (`base_url=f"{self.host}/v1"`, matching `OllamaProvider`'s
own call exactly). `chat()` parses the response as
`choices[0].message.content` (OpenAI shape), not Ollama's native
`message.content` — the two providers' non-structured paths differ here
because llama-server doesn't have an Ollama-style native `/api/chat`
endpoint to prefer instead.
