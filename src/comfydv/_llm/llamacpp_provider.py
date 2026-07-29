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

import asyncio
import logging
from collections.abc import Callable

from pydantic import BaseModel

from .ollama_provider import (
    _TTLLRUCache,
    _cache_key,
    _get_json,
    _pop_refusal_retry,
    _pop_think,
    _post_json,
)
from .provider import Message, ModelInfo, ModelStatus
from .retry import (
    RETRY_BACKOFF_SECS,
    format_recovered_status,
    format_retry_status,
    is_refusal,
    next_seed,
    next_timeout_secs,
    record_attempt_info,
)

logger = logging.getLogger(__name__)

# Own cache pool, not shared with OllamaProvider's — see plan.md's Structure
# Decision (parallel, symmetric, independent implementations). ChatCompletion
# is OUTPUT_NODE=True and re-executes every queue run regardless of which
# provider is wired in, so caching parity matters for llama.cpp too, not
# just Ollama.
_MODEL_LIST_CACHE = _TTLLRUCache(maxsize=32, ttl_seconds=20.0)
_CHAT_RESPONSE_CACHE = _TTLLRUCache(maxsize=64, ttl_seconds=None)


async def _fetch_models(host: str, headers: dict | None = None) -> list[str]:
    """Name-only view for ComfyUI's combo-widget population (the JS refresh
    button and node-creation auto-populate) — mirrors
    ollama_provider._fetch_models's narrower, gracefully-degrading contract.

    Deliberately more forgiving than LlamaCppProvider.list_models(): that
    method raises on a non-router-mode server (FR-006, for real workflow
    execution, where a silent empty result would be misleading). This
    combo-population use case wants the same quiet "just show an empty
    dropdown" degradation Ollama's nodes already give for *any* failure —
    consistent UX across backends for this specific, lower-stakes path.
    """
    try:
        models = await LlamaCppProvider(host, headers).list_models()
    except Exception as exc:
        logger.warning("Could not fetch llama.cpp models from %s: %s", host, exc)
        return []
    return [m.name for m in models]


def _to_openai_message(message: Message) -> dict:
    """Render a ``Message`` in llama.cpp's OpenAI-compatible shape.

    A text-only turn stays ``{"role", "content": <str>}`` — byte-identical to
    the pre-009 payload (FR-003). A turn carrying images becomes OpenAI
    multimodal ``content`` parts: the text followed by one ``image_url`` part
    per base64 image, as a ``data:`` URI (ADR-008). ``llama-server`` only
    honours these parts when launched with a multimodal projector
    (``--mmproj``); without it the server errors, surfaced to the caller
    rather than crashed on (FR-006).
    """
    if not message.images:
        return {"role": message.role, "content": message.content}
    parts: list[dict] = [{"type": "text", "text": message.content}]
    for image in message.images:
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image}"},
            }
        )
    return {"role": message.role, "content": parts}


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
        try:
            await _post_json(
                f"{self.host}/models/load",
                {"model": model},
                headers=self.headers,
            )
        except RuntimeError as exc:
            # Confirmed live: router mode's own /models/load is NOT
            # idempotent — it 400s "model is already running" rather than
            # the {"success": true} the contract assumed. The LLMProvider
            # protocol requires load_model() to be idempotent, so this
            # error is the desired end-state, not a failure — absorb it
            # here rather than leaking the wire-level quirk to callers.
            if "model is already running" not in str(exc):
                raise

    async def unload_model(self, model: str) -> None:
        if not model.strip():
            raise ValueError("model name cannot be empty")
        try:
            await _post_json(
                f"{self.host}/models/unload",
                {"model": model},
                headers=self.headers,
            )
        except RuntimeError as exc:
            # Mirror of load_model()'s non-idempotency above, confirmed live:
            # /models/unload 400s "model is not running" on an already-
            # unloaded model instead of {"success": true}.
            if "model is not running" not in str(exc):
                raise

    async def chat(
        self,
        model: str,
        messages: list[Message],
        options: dict | None = None,
        timeout_secs: float = 300.0,
        max_retries: int = 2,
        attempt_info: dict | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> str:
        payload_messages = [_to_openai_message(m) for m in messages]
        options, think = _pop_think(options)
        options, refusal_cfg = _pop_refusal_retry(options)
        embed_fn = None
        custom_phrases: tuple[str, ...] = ()
        if refusal_cfg and refusal_cfg.get("enabled"):
            custom_phrases = tuple(refusal_cfg.get("custom_phrases") or ())
            if refusal_cfg.get("embedding_model"):
                embedding_model = refusal_cfg["embedding_model"]
                embed_fn = lambda t: self.embed(embedding_model, t)  # noqa: E731
        total_attempts = max(0, min(int(max_retries), 5)) + 1
        response_text = ""
        refusal_count = 0
        attempt_seed = 0
        attempt_timeout = timeout_secs

        for attempt in range(1, total_attempts + 1):
            attempt_timeout = next_timeout_secs(timeout_secs, attempt)
            payload: dict = {
                "model": model,
                "messages": payload_messages,
                "stream": False,
            }
            if options:
                # Passed through verbatim, same nesting OllamaProvider.chat()
                # uses (payload["options"] = options) — the OllamaOption*
                # nodes emit Ollama-native parameter names (num_predict,
                # repeat_penalty, ...), which llama-server's OpenAI-compatible
                # endpoint won't recognize either way; translating them is
                # out of scope for this epic (plan.md Non-goals — no changes
                # to the generic nodes). This keeps the two providers'
                # handling consistent rather than silently special-casing
                # one of them.
                payload["options"] = options
            if think is not None:
                # ADR-010: llama-server's two documented reasoning toggles —
                # sourced from server docs, not live-verified (no instance
                # available at implementation time).
                payload["chat_template_kwargs"] = {"enable_thinking": think}
                if not think:
                    payload["reasoning_effort"] = "none"
            if attempt > 1:
                # Unlike the options-passthrough above, this IS the OpenAI
                # spec's actual top-level "seed" field, so it takes effect
                # against llama-server's /v1/chat/completions.
                payload["seed"] = next_seed(options, attempt)
                attempt_seed = payload["seed"]
            else:
                # attempt 1 never sets the top-level "seed" field above (only
                # retries do) — fall back to whatever the caller pinned in
                # options, so attempt_info/seed_used reports the real seed in
                # play even on a first-attempt success, not a stale 0.
                attempt_seed = (options or {}).get("seed", 0)

            cache_key = _cache_key(
                "llamacpp_chat",
                self.host,
                self.headers or {},
                model,
                payload_messages,
                options or {},
                think,
                payload.get("seed"),
            )
            cached, hit = _CHAT_RESPONSE_CACHE.get(cache_key)
            if hit:
                record_attempt_info(
                    attempt_info,
                    seed=attempt_seed,
                    attempts=attempt,
                    timeout_secs=attempt_timeout,
                    refusals=refusal_count,
                )
                return cached

            result = await _post_json(
                f"{self.host}/v1/chat/completions",
                payload,
                timeout=attempt_timeout,
                headers=self.headers,
            )
            choices = result.get("choices") or []
            response_text = (
                choices[0].get("message", {}).get("content", "") or ""
                if choices
                else ""
            )
            retry_reason: str | None = None
            if response_text.strip():
                refused = False
                if refusal_cfg and refusal_cfg.get("enabled"):
                    refused = await is_refusal(
                        response_text,
                        embed_fn=embed_fn,
                        embed_cache_key=refusal_cfg.get("embedding_model", ""),
                        threshold=refusal_cfg.get("threshold", 0.82),
                        custom_phrases=custom_phrases,
                    )
                if not refused:
                    _CHAT_RESPONSE_CACHE.set(cache_key, response_text)
                    record_attempt_info(
                        attempt_info,
                        seed=attempt_seed,
                        attempts=attempt,
                        timeout_secs=attempt_timeout,
                        refusals=refusal_count,
                    )
                    if on_status is not None and attempt > 1:
                        on_status(
                            format_recovered_status(
                                attempt, total_attempts, attempt_seed
                            )
                        )
                    return response_text
                refusal_count += 1
                retry_reason = "Refusal/deflection detected"
            else:
                retry_reason = "Blank response"

            if attempt < total_attempts:
                if on_status is not None:
                    upcoming_seed = next_seed(options, attempt + 1)
                    upcoming_timeout = next_timeout_secs(timeout_secs, attempt + 1)
                    on_status(
                        format_retry_status(
                            retry_reason,
                            attempt,
                            total_attempts,
                            upcoming_seed,
                            upcoming_timeout,
                        )
                    )
                await asyncio.sleep(RETRY_BACKOFF_SECS)

        record_attempt_info(
            attempt_info,
            seed=attempt_seed,
            attempts=total_attempts,
            timeout_secs=attempt_timeout,
            refusals=refusal_count,
        )
        # Every attempt came back blank — never raises here (chat() has
        # never validated its output, unlike chat_structured()); return the
        # last (blank) attempt uncached so the next queue run tries fresh.
        return response_text

    async def chat_structured(
        self,
        model: str,
        messages: list[Message],
        schema: type[BaseModel],
        options: dict | None = None,
        timeout_secs: float = 300.0,
        max_retries: int = 2,
        attempt_info: dict | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> BaseModel:
        from .chat import chat_structured as _chat_structured_impl

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
            record_attempt_info(
                attempt_info,
                seed=(options or {}).get("seed", 0),
                attempts=1,
                timeout_secs=timeout_secs,
                refusals=0,
            )
            return schema.model_validate(cached)

        embed_fn = None
        refusal_cfg = (options or {}).get("refusal_retry")
        if (
            refusal_cfg
            and refusal_cfg.get("enabled")
            and refusal_cfg.get("embedding_model")
        ):
            embedding_model = refusal_cfg["embedding_model"]
            embed_fn = lambda t: self.embed(embedding_model, t)  # noqa: E731

        result = await _chat_structured_impl(
            base_url=f"{self.host}/v1",
            model=model,
            messages=messages,
            schema=schema,
            headers=self.headers,
            options=options,
            max_retries=max_retries,
            timeout_secs=timeout_secs,
            embed_fn=embed_fn,
            attempt_info=attempt_info,
            on_status=on_status,
        )
        _CHAT_RESPONSE_CACHE.set(cache_key, result.model_dump())
        return result

    async def embed(self, model: str, text: str) -> list[float] | None:
        """POST {host}/v1/embeddings — llama-server's OpenAI-compatible
        embeddings endpoint.

        Requires an embedding-capable model to be loaded in the router
        (typically a *different* model from whatever's answering chat
        requests) — not live-verified against a running llama-server (no
        instance available at implementation time), mirroring this
        provider's other sourced-from-docs-not-verified caveats. Returns
        ``None`` rather than raising on any failure, same contract as
        ``OllamaProvider.embed()``.
        """
        if not model.strip() or not text.strip():
            return None
        try:
            result = await _post_json(
                f"{self.host}/v1/embeddings",
                {"model": model, "input": text},
                timeout=30.0,
                headers=self.headers,
            )
        except Exception:
            return None
        data = result.get("data")
        if not isinstance(data, list) or not data:
            return None
        vec = data[0].get("embedding")
        if not isinstance(vec, list) or not vec:
            return None
        return vec
