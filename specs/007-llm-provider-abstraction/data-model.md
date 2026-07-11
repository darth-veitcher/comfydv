# Data Model: LLM Provider Abstraction

## `ModelStatus` (enum)

Residency status of a model on a provider's server.

| Value | Meaning | Emitted by |
|---|---|---|
| `unloaded` | Known to the server, not resident in memory | all providers |
| `loading` | Transitioning into memory | all providers |
| `loaded` | Resident and ready to serve requests | all providers |
| `sleeping` | Resident but idle-parked | llama.cpp only; Ollama has no distinct signal for this via its API and normalizes resident-and-idle to `loaded` (documented approximation, ADR-007) |
| `downloading` | Server is fetching model weights | llama.cpp only; `OllamaProvider` never emits this (Ollama's pull/download flow is out of scope, per the original Ollama epic's non-goals) |

## `ModelInfo`

One entry returned by `list_models()`.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Model identifier as the provider's server knows it |
| `status` | `ModelStatus` | See above |
| `size` | `int \| None` | Bytes, if the provider reports it; `None` otherwise |

## `LLMProvider` (Protocol)

The adapter boundary. Every backend (`OllamaProvider` now, `LlamaCppProvider`
in the follow-on epic) implements this shape; ComfyUI nodes depend only on
the protocol, never on a concrete provider class.

| Method | Signature | Notes |
|---|---|---|
| `list_models` | `async def list_models(self) -> list[ModelInfo]` | |
| `load_model` | `async def load_model(self, model: str) -> None` | Idempotent: loading an already-loaded model is not an error |
| `unload_model` | `async def unload_model(self, model: str) -> None` | Idempotent: unloading an already-unloaded model is not an error |
| `chat` | `async def chat(self, model: str, messages: list[Message], options: dict) -> str` | Free-text response |
| `chat_structured` | `async def chat_structured(self, model: str, messages: list[Message], schema: type[BaseModel], options: dict) -> BaseModel` | Validated response; raises on exhausted retries (see FR-004) |

A concrete provider instance is constructed once per ComfyUI client node with
its connection's host/headers as instance state (Constitution Principle V
justification — see `research.md`), and that instance is the value carried
by the `LLM_CLIENT` ComfyUI socket type.

## `Message`

One turn in a chat request, matching the existing shape already sent to
Ollama's `/api/chat`/`/v1/chat/completions` (`role` + `content`); unchanged
by this feature, carried forward as-is.

| Field | Type | Notes |
|---|---|---|
| `role` | `Literal["system", "user", "assistant"]` | |
| `content` | `str` | |

## Relationships

```
ProviderConnection (ComfyUI client node)
  └─ produces → LLM_CLIENT socket value (an LLMProvider instance)
       └─ consumed by → LLMModelSelector, LLMLoadModel, LLMUnloadModel, ChatCompletion (ComfyUI nodes)
            ├─ list_models() → ModelInfo[]
            ├─ load_model()/unload_model() → mutates server-side residency, no return value
            └─ chat()/chat_structured() → str | BaseModel
```

No new persistent storage is introduced — every entity above is
constructed per-request or per-node-execution from the connected server's
live state; the only caching is the existing in-memory TTL cache for model
listing (`_TTLLRUCache`, unchanged, reused inside `OllamaProvider`).
