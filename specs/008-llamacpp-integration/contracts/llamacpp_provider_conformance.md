# Contract: `LlamaCppProvider` conforms to `LLMProvider`

This is the concrete proof of ADR-007's adapter pattern — the same protocol
contract documented in
`specs/007-llm-provider-abstraction/contracts/llm_provider_protocol.md`,
now with a second implementation. Nothing in that contract changes; this
file only documents `LlamaCppProvider`'s specific wire-format bindings.

```python
class LlamaCppProvider:
    def __init__(self, host: str, headers: dict | None = None): ...

    async def list_models(self) -> list[ModelInfo]:
        """GET {host}/models → data[] → ModelInfo(name=m["id"], status=ModelStatus(m["status"]["value"]), size=None)"""

    async def load_model(self, model: str) -> None:
        """POST {host}/models/load {"model": model}"""

    async def unload_model(self, model: str) -> None:
        """POST {host}/models/unload {"model": model}"""

    async def chat(self, model, messages, options=None, timeout_secs=300.0) -> str:
        """POST {host}/v1/chat/completions → choices[0].message.content"""

    async def chat_structured(self, model, messages, schema, options=None, timeout_secs=300.0, max_retries=2) -> BaseModel:
        """Delegates to comfydv._llm.chat.chat_structured(base_url=f"{host}/v1", ...) — identical call OllamaProvider makes"""
```

## Behavioral requirements (inherited from the protocol contract, restated for this implementation)

- `load_model`/`unload_model` MUST be idempotent — router mode's own
  `{"success": true}` response on an already-loaded/unloaded model satisfies
  this without extra handling.
- `list_models()` MUST NOT normalize away llama.cpp's `sleeping`/`downloading`
  states (unlike `OllamaProvider`, which has no choice but to normalize —
  see `research.md`).
- A `llama-server` not running in router mode (missing endpoints) MUST
  surface a clear, specific error (spec.md FR-006) — not a generic
  connection failure indistinguishable from "server not running at all."
