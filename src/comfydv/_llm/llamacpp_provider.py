"""LlamaCppProvider — LLMProvider implementation backed by llama-server's
router mode.

Mirrors comfydv._llm.ollama_provider's structure exactly (ADR-007's parallel-
implementation pattern). Router-mode API shape verified live against
ggml-org/llama.cpp's tools/server/README.md (postdates training data) — see
specs/008-llamacpp-integration/research.md. Two details differ from Ollama:
the model identifier field is "id" (not "name"), and "status" is a nested
object ({"value": "..."}), not a flat string.

Deployment prerequisite: llama-server must be launched with --models-dir or
--models-preset (router mode) — the endpoints this provider calls don't
exist otherwise (spec.md FR-006).
"""

import logging

from pydantic import BaseModel

from comfydv._llm.ollama_provider import _TTLLRUCache, _cache_key, _get_json, _post_json
from comfydv._llm.provider import Message, ModelInfo, ModelStatus

logger = logging.getLogger(__name__)

# Own cache pool, not shared with OllamaProvider's — see plan.md's Structure
# Decision (parallel, symmetric, independent implementations). ChatCompletion
# is OUTPUT_NODE=True and re-executes every queue run regardless of which
# provider is wired in, so caching parity matters for llama.cpp too, not
# just Ollama.
_MODEL_LIST_CACHE = _TTLLRUCache(maxsize=32, ttl_seconds=20.0)
_CHAT_RESPONSE_CACHE = _TTLLRUCache(maxsize=64, ttl_seconds=None)


class LlamaCppProvider:
    """LLMProvider implementation backed by llama-server's router mode.

    Host and headers are captured once at construction — every method
    reuses them, the same pattern OllamaProvider already established.
    """

    def __init__(self, host: str, headers: dict | None = None):
        self.host = host
        self.headers = dict(headers) if headers else None

    async def list_models(self) -> list[ModelInfo]:
        """GET {host}/models — every model llama-server's router knows
        about, with its live status. Unlike OllamaProvider, no
        normalization is needed: llama.cpp's status vocabulary is exactly
        ModelStatus's full set.
        """
        cache_key = _cache_key("llamacpp_list_models", self.host, self.headers or {})
        cached, hit = _MODEL_LIST_CACHE.get(cache_key)
        if hit:
            return cached

        try:
            data = await _get_json(f"{self.host}/models", headers=self.headers)
        except OSError as exc:
            # Genuinely unreachable (connection refused, DNS failure, timed
            # out — aiohttp's connection-level exceptions are all OSError
            # subclasses) — degrade gracefully like OllamaProvider does, so
            # a not-yet-started server just shows an empty dropdown rather
            # than a hard error.
            logger.warning(
                "Could not fetch llama.cpp models from %s: %s", self.host, exc
            )
            return []
        except RuntimeError as exc:
            # The server answered but with an HTTP error status — GET
            # /models only exists in router mode, so this is almost always
            # a llama-server launched without --models-dir/--models-preset.
            # Surfacing this distinctly (FR-006) matters: silently returning
            # [] here would be indistinguishable from "no models installed".
            raise RuntimeError(
                f"llama-server at {self.host} did not return a model list from "
                f"GET {self.host}/models — is it running in router mode "
                f"(--models-dir or --models-preset)? Underlying error: {exc}"
            ) from exc

        models = []
        for m in data.get("data", []):
            status_value = m.get("status", {}).get("value")
            try:
                status = ModelStatus(status_value)
            except ValueError:
                logger.warning(
                    "llama.cpp reported an unrecognized model status %r for %r — "
                    "skipping status normalization, this model will be omitted",
                    status_value,
                    m.get("id"),
                )
                continue
            models.append(ModelInfo(name=m["id"], status=status, size=None))
        if models:
            _MODEL_LIST_CACHE.set(cache_key, models)
        return models

    async def load_model(self, model: str) -> None:
        if not model.strip():
            raise ValueError("model name cannot be empty")
        await _post_json(
            f"{self.host}/models/load",
            {"model": model},
            headers=self.headers,
        )

    async def unload_model(self, model: str) -> None:
        if not model.strip():
            raise ValueError("model name cannot be empty")
        await _post_json(
            f"{self.host}/models/unload",
            {"model": model},
            headers=self.headers,
        )

    async def chat(
        self,
        model: str,
        messages: list[Message],
        options: dict | None = None,
        timeout_secs: float = 300.0,
    ) -> str:
        payload_messages = [m.model_dump() for m in messages]
        payload: dict = {"model": model, "messages": payload_messages, "stream": False}
        if options:
            # Passed through verbatim, same nesting OllamaProvider.chat() uses
            # (payload["options"] = options) — the OllamaOption* nodes emit
            # Ollama-native parameter names (num_predict, repeat_penalty,
            # ...), which llama-server's OpenAI-compatible endpoint won't
            # recognize either way; translating them is out of scope for
            # this epic (plan.md Non-goals — no changes to the generic
            # nodes). This keeps the two providers' handling consistent
            # rather than silently special-casing one of them.
            payload["options"] = options

        cache_key = _cache_key(
            "llamacpp_chat",
            self.host,
            self.headers or {},
            model,
            payload_messages,
            options or {},
        )
        cached, hit = _CHAT_RESPONSE_CACHE.get(cache_key)
        if hit:
            return cached

        result = await _post_json(
            f"{self.host}/v1/chat/completions",
            payload,
            timeout=timeout_secs,
            headers=self.headers,
        )
        choices = result.get("choices") or []
        response_text = (
            choices[0].get("message", {}).get("content", "") or "" if choices else ""
        )
        _CHAT_RESPONSE_CACHE.set(cache_key, response_text)
        return response_text

    async def chat_structured(
        self,
        model: str,
        messages: list[Message],
        schema: type[BaseModel],
        options: dict | None = None,
        timeout_secs: float = 300.0,
        max_retries: int = 2,
    ) -> BaseModel:
        from comfydv._llm.chat import chat_structured as _chat_structured_impl

        payload_messages = [m.model_dump() for m in messages]
        cache_key = _cache_key(
            "llamacpp_chat_structured",
            self.host,
            self.headers or {},
            model,
            payload_messages,
            options or {},
            schema.model_json_schema(),
        )
        cached, hit = _CHAT_RESPONSE_CACHE.get(cache_key)
        if hit:
            return schema.model_validate(cached)

        result = await _chat_structured_impl(
            base_url=f"{self.host}/v1",
            model=model,
            messages=messages,
            schema=schema,
            headers=self.headers,
            options=options,
            max_retries=max_retries,
            timeout_secs=timeout_secs,
        )
        _CHAT_RESPONSE_CACHE.set(cache_key, result.model_dump())
        return result
