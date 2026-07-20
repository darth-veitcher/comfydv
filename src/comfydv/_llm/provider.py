"""LLMProvider protocol — the adapter boundary between ComfyUI nodes and
specific local inference backends.

ADR-007: every backend (OllamaProvider now, LlamaCppProvider in a follow-on
epic) implements this shape; ComfyUI nodes depend only on the protocol,
never on a concrete provider class. See
project-management/ADRs/ADR-007-llm-provider-adapter-pattern.md and
specs/007-llm-provider-abstraction/contracts/llm_provider_protocol.md.
"""

from enum import Enum
from typing import Literal, Protocol

from pydantic import BaseModel


class ModelStatus(str, Enum):
    """Residency status of a model on a provider's server.

    Not every provider emits every value — e.g. Ollama has no distinct
    signal for SLEEPING or DOWNLOADING via its API and normalizes to the
    closest applicable status rather than omitting the model (documented
    approximation, ADR-007).
    """

    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    SLEEPING = "sleeping"
    DOWNLOADING = "downloading"


class ModelInfo(BaseModel):
    """One entry returned by ``LLMProvider.list_models()``."""

    name: str
    status: ModelStatus
    size: int | None = None


class Message(BaseModel):
    """One turn in a chat request."""

    role: Literal["system", "user", "assistant"]
    content: str


class LLMProvider(Protocol):
    """Adapter boundary every backend implements.

    Connection state (host, auth headers, or equivalent) is captured once
    at provider-construction time — no method takes connection details as
    a parameter.
    """

    async def list_models(self) -> list[ModelInfo]:
        """Every model the server currently knows about, loaded or not."""
        ...

    async def load_model(self, model: str) -> None:
        """Load a model into memory. Idempotent — already-loaded is not an error."""
        ...

    async def unload_model(self, model: str) -> None:
        """Unload a model from memory. Idempotent — already-unloaded is not an error."""
        ...

    async def chat(
        self,
        model: str,
        messages: list[Message],
        options: dict | None = None,
        timeout_secs: float = 300.0,
        max_retries: int = 2,
    ) -> str:
        """Free-text chat response.

        Retries up to ``max_retries`` times (clamped 0-5) with a new seed if
        the response comes back blank — confirmed live on a freshly-loaded
        model, whose first response is sometimes empty before it settles
        into normal behavior. Still returns the (possibly blank) last
        attempt's text rather than raising if every retry comes back blank —
        this method has never validated its output, unlike
        ``chat_structured()``.
        """
        ...

    async def chat_structured(
        self,
        model: str,
        messages: list[Message],
        schema: type[BaseModel],
        options: dict | None = None,
        timeout_secs: float = 300.0,
        max_retries: int = 2,
    ) -> BaseModel:
        """Schema-validated chat response.

        Raises ``RuntimeError`` (naming the model, attempt count, and a
        truncated snippet of the last invalid response) if every retry is
        exhausted — never returns a value with a missing/blank required
        field.
        """
        ...
