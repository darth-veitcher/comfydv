# Contract: `LLMProvider` protocol

This is the interface the follow-on `llamacpp-integration` epic implements
against (`LlamaCppProvider`) — it's the actual deliverable that makes ADR-007's
adapter pattern real, not internal implementation detail. Treat changes to
this contract as requiring epic-level sign-off (per ADR-007's own scope),
not a routine refactor.

```python
class ModelStatus(str, Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    SLEEPING = "sleeping"      # not all providers emit this
    DOWNLOADING = "downloading"  # not all providers emit this

class ModelInfo(BaseModel):
    name: str
    status: ModelStatus
    size: int | None = None

class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class LLMProvider(Protocol):
    async def list_models(self) -> list[ModelInfo]: ...
    async def load_model(self, model: str) -> None: ...
    async def unload_model(self, model: str) -> None: ...
    async def chat(
        self, model: str, messages: list[Message], options: dict | None = None,
        timeout_secs: float = 300.0,
    ) -> str: ...
    async def chat_structured(
        self, model: str, messages: list[Message], schema: type[BaseModel],
        options: dict | None = None, timeout_secs: float = 300.0, max_retries: int = 2,
    ) -> BaseModel: ...
```

## Behavioral requirements (every implementation MUST satisfy)

- `load_model`/`unload_model` are **idempotent** — calling either on a model
  already in that state is not an error.
- `chat_structured` **MUST NOT** return a `BaseModel` instance with a blank
  required `str` field — validate and retry (bounded, provider-internal)
  rather than pass through invalid data. On exhausted retries, raise
  `RuntimeError` naming the model, attempt count, and a truncated snippet of
  the last invalid response (FR-004 in `../spec.md`).
- `list_models` MUST return every model the server currently knows about,
  including ones not currently loaded — this is a status listing, not a
  "loaded models only" filter.
- A provider that cannot represent a given `ModelStatus` value (e.g. Ollama
  has no `sleeping`/`downloading` concept) MUST normalize to the closest
  applicable status rather than omit the model or invent a new status value
  outside this enum.
- Connection state (host, auth headers, or equivalent) is captured once at
  provider-construction time; no method takes connection details as a
  parameter.

## Non-requirements (explicitly not part of this contract)

- No requirement that every provider support every `ModelStatus` value —
  see `data-model.md`'s per-provider emission notes.
- No streaming contract — `chat`/`chat_structured` return a complete result,
  not a stream. (Not requested by the parent spec; a future contract change
  if ever needed.)
- No multi-turn agent/tool-use contract beyond a single structured-output
  call — out of scope per the parent epic's Non-goals.

## ComfyUI-facing contract: `LLM_CLIENT` socket

An `LLMProvider`-implementing instance is the value carried by ComfyUI's
`LLM_CLIENT` custom socket type. Any node that outputs `LLM_CLIENT` (e.g.
`OllamaClient`, and later `LlamaCppClient`) is committing to have constructed
a fully-configured provider instance — no partial/lazy construction that
defers connection details to the consuming node.

Generic nodes (`LLMModelSelector`, `LLMLoadModel`, `LLMUnloadModel`,
`ChatCompletion`) accept `LLM_CLIENT` as their only connection-related input
and MUST NOT branch on which concrete provider type they received — doing so
would defeat the point of the protocol boundary (ADR-007).
