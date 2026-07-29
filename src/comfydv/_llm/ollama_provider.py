"""OllamaProvider — LLMProvider implementation backed by Ollama's REST API.

Ported from comfydv.ollama's original module-level HTTP/cache helpers
(_post_json, _fetch_models, _run_async, _TTLLRUCache) — behavior-preserving,
not a rewrite. See ADR-007 and
specs/007-llm-provider-abstraction/research.md.

OllamaProvider implements the LLMProvider Protocol structurally (no explicit
inheritance — that's the point of typing.Protocol); conformance is checked
by ``ty check``, not the runtime.
"""

import asyncio
import json
import logging
import threading
import time

from pydantic import BaseModel, ValidationError

from .provider import Message, ModelInfo, ModelStatus
from .retry import (
    RETRY_BACKOFF_SECS,
    is_refusal,
    next_seed,
    next_timeout_secs,
    record_attempt_info,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Local response cache (ported from comfydv.ollama)
# ---------------------------------------------------------------------------
#
# See comfydv.ollama's original module docstring for why this exists:
# OUTPUT_NODE=True chat nodes re-execute every queue run even when inputs
# are unchanged; this cache absorbs the redundant round-trips.


class _TTLLRUCache:
    """Bounded cache, LRU-evicted, with an optional per-entry TTL."""

    def __init__(self, maxsize: int, ttl_seconds: float | None = None):
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._data: dict = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None, False
            expires_at, value = entry
            if self.ttl_seconds is not None and time.monotonic() > expires_at:
                del self._data[key]
                return None, False
            # Re-insert to mark as most-recently-used (dicts preserve insertion order).
            del self._data[key]
            self._data[key] = (expires_at, value)
            return value, True

    def set(self, key, value):
        with self._lock:
            expires_at = (
                time.monotonic() + self.ttl_seconds
                if self.ttl_seconds is not None
                else float("inf")
            )
            self._data.pop(key, None)
            self._data[key] = (expires_at, value)
            while len(self._data) > self.maxsize:
                oldest_key = next(iter(self._data))
                del self._data[oldest_key]

    def clear(self):
        with self._lock:
            self._data.clear()


def _cache_key(*parts) -> str:
    """Deterministic, hashable key from arbitrary JSON-serializable parts."""
    return json.dumps(parts, sort_keys=True, default=str)


def _pop_think(options: dict | None) -> tuple[dict | None, bool | None]:
    """Split a ``"think"`` toggle out of a generic ``options`` dict.

    ADR-010: ``OllamaOptionDisableThinking`` merges a ``"think": bool`` key
    into the same composable ``OLLAMA_OPTIONS`` chain every other
    ``OllamaOption*`` node feeds into ``ChatCompletion``'s ``options``
    input — but unlike those (Ollama-native sampling params, passed through
    verbatim), ``"think"`` needs real per-provider translation: neither
    Ollama's native ``/api/chat`` nor llama-server's OpenAI-compatible
    endpoint recognizes a literal ``"think"`` key nested inside their own
    ``options``/sampling-params object, so every provider pops it out here
    (or in ``LlamaCppProvider``'s own copy) before building its request.
    Returns ``options`` with ``"think"`` removed (unchanged if absent, so a
    falsy/empty result stays falsy) and the popped value, or ``None`` if the
    caller didn't set it — never touches the caller's own dict in place.
    """
    if not options or "think" not in options:
        return options, None
    remaining = dict(options)
    think = remaining.pop("think")
    return (remaining or None), think


def _pop_refusal_retry(options: dict | None) -> tuple[dict | None, dict | None]:
    """Split a ``"refusal_retry"`` config dict out of a generic ``options``
    dict — same convention as ``_pop_think``: ``OllamaOptionRefusalRetry``
    merges ``{"refusal_retry": {"enabled", "embedding_model", "threshold"}}``
    into the same composable ``OLLAMA_OPTIONS`` chain every other
    ``OllamaOption*`` node feeds into ``ChatCompletion``'s ``options``
    input, and neither Ollama's nor llama.cpp's own API recognizes this key,
    so every provider pops it out here before building its request.
    """
    if not options or "refusal_retry" not in options:
        return options, None
    remaining = dict(options)
    cfg = remaining.pop("refusal_retry")
    return (remaining or None), cfg


_MODEL_LIST_CACHE = _TTLLRUCache(maxsize=32, ttl_seconds=20.0)
_CHAT_RESPONSE_CACHE = _TTLLRUCache(maxsize=64, ttl_seconds=None)
_CAPABILITY_CACHE = _TTLLRUCache(maxsize=32, ttl_seconds=300.0)


# ---------------------------------------------------------------------------
# Async infrastructure (ported from comfydv.ollama)
# ---------------------------------------------------------------------------


def _run_async(coro):
    """Run an async coroutine synchronously in an isolated worker thread.

    Always spins up a fresh thread rather than conditionally checking
    asyncio.get_running_loop() first: live-verified against a real running
    ComfyUI instance (its execution engine runs its own event loop, in
    Python 3.13, on the same process) that the conditional version — try
    get_running_loop(), spin up a thread only if it succeeds, otherwise
    call asyncio.run(coro) directly — is unreliable there. Under real
    ComfyUI, get_running_loop() sometimes raised inside that try block
    (unlike under pytest or a standalone script, where it never does),
    which routed straight into `asyncio.run(coro)` on the *current* thread
    — the one thread guaranteed to already have ComfyUI's own loop running
    — reproducing exactly the "asyncio.run() cannot be called from a
    running event loop" crash this function exists to prevent. Always
    using a dedicated thread sidesteps the detection entirely: a freshly
    spawned thread never has an ambient loop, so asyncio.run() is safe
    there unconditionally, regardless of what the calling thread's loop
    state actually is.
    """
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _post_json(
    url: str,
    payload: dict,
    *,
    timeout: float = 120.0,
    headers: dict | None = None,
) -> dict:
    """POST JSON to url, return parsed response dict."""
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers or None,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    raise RuntimeError(
                        f"Ollama returned HTTP {resp.status} for {url}: {body[:300]}"
                    )
                return await resp.json()
    except aiohttp.ClientConnectionError as exc:
        raise RuntimeError(f"Cannot reach Ollama at {url}: {exc}") from exc


async def _get_json(
    url: str, *, timeout: float = 5.0, headers: dict | None = None
) -> dict:
    """GET url, return parsed response dict.

    Raises RuntimeError on an HTTP error status (distinct message, so callers
    can tell "server responded with an error" from "couldn't reach it at
    all" — aiohttp connection/timeout errors propagate unwrapped for that
    reason). Message is generic, not backend-branded: this helper is shared
    by every LLMProvider implementation.
    """
    import aiohttp

    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            headers=headers or None,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            if resp.status >= 400:
                body = await resp.text()
                raise RuntimeError(
                    f"Server returned HTTP {resp.status} for {url}: {body[:300]}"
                )
            return await resp.json()


async def _fetch_models(host: str, headers: dict | None = None) -> list[str]:
    """GET {host}/api/tags — return list of model name strings.

    Used by comfydv.ollama's combo-widget population (_load_default_models,
    the /dv/ollama/models route) — a narrower, name-only view than
    OllamaProvider.list_models(), which returns full ModelInfo with status.
    Cached for _MODEL_LIST_CACHE.ttl_seconds per (host, headers) pair.
    """
    cache_key = _cache_key("models", host, headers or {})
    cached, hit = _MODEL_LIST_CACHE.get(cache_key)
    if hit:
        return cached

    try:
        data = await _get_json(f"{host}/api/tags", headers=headers)
        models = [m["name"] for m in data.get("models", [])]
    except Exception as exc:
        logger.warning("Could not fetch Ollama models from %s: %s", host, exc)
        return []

    if models:
        _MODEL_LIST_CACHE.set(cache_key, models)
    return models


async def _require_vision_capability(
    host: str, model: str, headers: dict | None
) -> None:
    """Raise a clear error if ``model`` lacks Ollama's ``vision`` capability.

    Only called when a request carries at least one image (spec 009 FR-006):
    Ollama's /api/chat silently accepts an unsupported ``images`` field and
    answers with a blank/malformed HTTP 200 instead of an error — which
    would otherwise be indistinguishable from an ordinary blank generation
    and get swallowed by chat()'s existing blank-response retry. /api/show's
    ``capabilities`` list is the only place Ollama states support explicitly,
    so a request carrying an image is checked against it up front.

    Fails open on any lookup problem (older Ollama without ``capabilities``,
    unreachable host, unexpected shape) — a lookup failure must not block a
    request that would otherwise have worked; the real request surfaces its
    own clear error if the host is genuinely unreachable.
    """
    cache_key = _cache_key("capabilities", host, headers or {}, model)
    cached, hit = _CAPABILITY_CACHE.get(cache_key)
    if hit:
        capabilities = cached
    else:
        try:
            data = await _post_json(
                f"{host}/api/show", {"model": model}, timeout=10.0, headers=headers
            )
        except Exception:
            return
        capabilities = data.get("capabilities")
        if capabilities is None:
            return
        _CAPABILITY_CACHE.set(cache_key, capabilities)

    if "vision" not in capabilities:
        raise ValueError(
            f"Model '{model}' does not support image input — Ollama reports "
            f"capabilities {capabilities!r} for it, no 'vision'. Wire a "
            "vision-capable model, or disconnect the image input for "
            "text-only chat."
        )


class OllamaProvider:
    """LLMProvider implementation backed by Ollama's REST API.

    Host and headers are captured once at construction — every method
    reuses them, matching the ADR-005 config-node pattern (one
    ``OllamaClient`` node's output is one ``OllamaProvider`` instance).
    """

    def __init__(self, host: str, headers: dict | None = None):
        self.host = host
        self.headers = dict(headers) if headers else None

    async def list_models(self) -> list[ModelInfo]:
        """Every installed model, with live loaded/unloaded status.

        `/api/tags` lists installed models; `/api/ps` lists currently-loaded
        ones. Ollama has no `sleeping`/`downloading` concept via this API —
        never emitted here (ADR-007's documented approximation).
        """
        cache_key = _cache_key("list_models", self.host, self.headers or {})
        cached, hit = _MODEL_LIST_CACHE.get(cache_key)
        if hit:
            return cached

        try:
            tags = await _get_json(f"{self.host}/api/tags", headers=self.headers)
        except Exception as exc:
            logger.warning("Could not fetch Ollama models from %s: %s", self.host, exc)
            return []

        loaded_names: set[str] = set()
        try:
            ps = await _get_json(f"{self.host}/api/ps", headers=self.headers)
            loaded_names = {m["name"] for m in ps.get("models", [])}
        except Exception as exc:
            logger.warning(
                "Could not fetch Ollama running models from %s: %s", self.host, exc
            )

        models = [
            ModelInfo(
                name=m["name"],
                status=(
                    ModelStatus.LOADED
                    if m["name"] in loaded_names
                    else ModelStatus.UNLOADED
                ),
                size=m.get("size"),
            )
            for m in tags.get("models", [])
        ]
        if models:
            _MODEL_LIST_CACHE.set(cache_key, models)
        return models

    async def load_model(self, model: str) -> None:
        if not model.strip():
            raise ValueError("model name cannot be empty")
        await _post_json(
            f"{self.host}/api/generate",
            {"model": model, "keep_alive": -1, "stream": False},
            timeout=300.0,
            headers=self.headers,
        )

    async def unload_model(self, model: str) -> None:
        if not model.strip():
            raise ValueError("model name cannot be empty")
        await _post_json(
            f"{self.host}/api/generate",
            {"model": model, "keep_alive": 0, "stream": False},
            timeout=30.0,
            headers=self.headers,
        )

    async def chat(
        self,
        model: str,
        messages: list[Message],
        options: dict | None = None,
        timeout_secs: float = 300.0,
        max_retries: int = 2,
        attempt_info: dict | None = None,
    ) -> str:
        if any(m.images for m in messages):
            await _require_vision_capability(self.host, model, self.headers)

        # exclude_none drops the images key for text-only turns so an
        # image-less request is byte-identical to the pre-009 payload
        # (FR-003); a turn with images keeps Ollama's native flat images
        # array (ADR-008 — no transform needed for /api/chat).
        payload_messages = [m.model_dump(exclude_none=True) for m in messages]
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
        incomplete = False
        refusal_count = 0
        attempt_seed = 0
        attempt_timeout = timeout_secs

        for attempt in range(1, total_attempts + 1):
            attempt_options = dict(options) if options else {}
            if attempt > 1:
                attempt_options["seed"] = next_seed(options, attempt)
            attempt_seed = attempt_options.get("seed", 0)
            attempt_timeout = next_timeout_secs(timeout_secs, attempt)

            payload: dict = {
                "model": model,
                "messages": payload_messages,
                "stream": False,
            }
            if attempt_options:
                payload["options"] = attempt_options
            if think is not None:
                # ADR-010: confirmed live this must be a top-level field —
                # Ollama silently ignores "think" nested inside "options".
                payload["think"] = think

            cache_key = _cache_key(
                "chat",
                self.host,
                self.headers or {},
                model,
                payload_messages,
                attempt_options,
                think,
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
                f"{self.host}/api/chat",
                payload,
                timeout=attempt_timeout,
                headers=self.headers,
            )
            response_text = result.get("message", {}).get("content", "")
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
                    return response_text
                # A detected refusal is handled exactly like a blank
                # response below: fall through to the backoff/retry with a
                # bumped seed (next_seed), rather than returning the refusal
                # text to the caller.
                refusal_count += 1

            # done: false alongside blank content is a distinct signal from
            # an ordinary blank generation — it's Ollama answering before
            # the model has actually finished loading/swapping in, observed
            # live under model-swap load (issue #27), not the model having
            # genuinely generated nothing. Tracked separately so it can be
            # raised on below instead of silently returned like a real
            # blank generation would be.
            incomplete = result.get("done") is False

            if attempt < total_attempts:
                await asyncio.sleep(RETRY_BACKOFF_SECS)

        record_attempt_info(
            attempt_info,
            seed=attempt_seed,
            attempts=total_attempts,
            timeout_secs=attempt_timeout,
            refusals=refusal_count,
        )

        if incomplete:
            raise RuntimeError(
                f"Ollama returned an incomplete response after "
                f"{total_attempts} attempt(s) for model '{model}' — it may "
                "still be loading or swapping in memory. Try again in a "
                "few seconds."
            )

        # Every attempt came back blank (and complete) — never raises here
        # (chat() has never validated its output, unlike chat_structured());
        # return the last (blank) attempt uncached so the next queue run
        # tries fresh.
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
    ) -> BaseModel:
        """Native ``/api/chat`` + ``"format"`` (grammar-constrained JSON
        decoding), not the shared pydantic-ai ``chat.py`` helper.

        ADR-009 originally routed this through the OpenAI-compatible
        ``/v1/chat/completions`` endpoint via pydantic-ai's ``NativeOutput``.
        Confirmed live that endpoint silently *reloads the model at its
        default context size on every call*, discarding any prior
        ``options.num_ctx`` — even when the same ``options`` are included in
        that very request. Priming with a separate native call first
        (the original fix) didn't help: the very next OpenAI-compat call
        undid it immediately. The native ``/api/chat`` endpoint doesn't
        have this problem — confirmed live it preserves an already-primed
        context, and it supports structured output directly via
        ``"format"``, so ``options`` and structured output now apply
        atomically in one request. ``LlamaCppProvider`` is unaffected — it
        keeps using the shared pydantic-ai path, since llama-server's
        context is fixed at process launch, not a per-request concern.
        """
        if any(m.images for m in messages):
            await _require_vision_capability(self.host, model, self.headers)

        payload_messages = [m.model_dump(exclude_none=True) for m in messages]
        json_schema = schema.model_json_schema()
        options, think = _pop_think(options)
        options, refusal_cfg = _pop_refusal_retry(options)
        embed_fn = None
        custom_phrases: tuple[str, ...] = ()
        if refusal_cfg and refusal_cfg.get("enabled"):
            custom_phrases = tuple(refusal_cfg.get("custom_phrases") or ())
            if refusal_cfg.get("embedding_model"):
                embedding_model = refusal_cfg["embedding_model"]
                embed_fn = lambda t: self.embed(embedding_model, t)  # noqa: E731
        cache_key = _cache_key(
            "chat_structured",
            self.host,
            self.headers or {},
            model,
            payload_messages,
            options or {},
            json_schema,
            think,
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

        total_attempts = max(0, min(int(max_retries), 5)) + 1
        last_error: Exception | None = None
        last_invalid_text = ""
        refusal_count = 0
        attempt_seed = 0
        attempt_timeout = timeout_secs

        for attempt in range(1, total_attempts + 1):
            attempt_options = dict(options) if options else {}
            if attempt > 1:
                attempt_options["seed"] = next_seed(options, attempt)
            attempt_seed = attempt_options.get("seed", 0)
            attempt_timeout = next_timeout_secs(timeout_secs, attempt)

            payload: dict = {
                "model": model,
                "messages": payload_messages,
                "format": json_schema,
                "stream": False,
            }
            if attempt_options:
                payload["options"] = attempt_options
            if think is not None:
                # ADR-010: confirmed live this must be a top-level field —
                # Ollama silently ignores "think" nested inside "options".
                payload["think"] = think

            try:
                result = await _post_json(
                    f"{self.host}/api/chat",
                    payload,
                    timeout=attempt_timeout,
                    headers=self.headers,
                )
            except RuntimeError as exc:
                last_error = exc
                last_invalid_text = str(exc)
                if attempt < total_attempts:
                    await asyncio.sleep(RETRY_BACKOFF_SECS)
                continue

            content = result.get("message", {}).get("content", "")
            try:
                parsed = schema.model_validate_json(content)
            except ValidationError as exc:
                last_error = exc
                last_invalid_text = content
                if attempt < total_attempts:
                    await asyncio.sleep(RETRY_BACKOFF_SECS)
                continue

            if refusal_cfg and refusal_cfg.get("enabled"):
                # Checked against the raw JSON text, not a specific parsed
                # field: ChatCompletion's schema is caller-defined and this
                # provider has no idea which field would carry refusal
                # language — the regex/embedding check still matches text
                # sitting inside a JSON string value either way.
                refused = await is_refusal(
                    content,
                    embed_fn=embed_fn,
                    embed_cache_key=refusal_cfg.get("embedding_model", ""),
                    threshold=refusal_cfg.get("threshold", 0.82),
                    custom_phrases=custom_phrases,
                )
                if refused:
                    refusal_count += 1
                    last_error = RuntimeError("refusal/deflection detected")
                    last_invalid_text = content
                    if attempt < total_attempts:
                        await asyncio.sleep(RETRY_BACKOFF_SECS)
                    continue

            _CHAT_RESPONSE_CACHE.set(cache_key, parsed.model_dump())
            record_attempt_info(
                attempt_info,
                seed=attempt_seed,
                attempts=attempt,
                timeout_secs=attempt_timeout,
                refusals=refusal_count,
            )
            return parsed

        record_attempt_info(
            attempt_info,
            seed=attempt_seed,
            attempts=total_attempts,
            timeout_secs=attempt_timeout,
            refusals=refusal_count,
        )
        raise RuntimeError(
            f"chat_structured: response failed validation against schema after "
            f"{total_attempts} attempt(s) (model={model!r}). Last error: "
            f"{last_error}. Last response (truncated): {last_invalid_text[:300]!r}"
        )

    async def embed(self, model: str, text: str) -> list[float] | None:
        """POST {host}/api/embed — Ollama's native embeddings endpoint.

        Returns ``None`` rather than raising on any failure (wrong/missing
        embedding model, unreachable server, malformed response) — this is
        a best-effort capability per the ``LLMProvider`` protocol, and its
        one current caller (refusal-retry detection) already treats
        ``None`` as "skip the embedding check", not an error.
        """
        if not model.strip() or not text.strip():
            return None
        try:
            result = await _post_json(
                f"{self.host}/api/embed",
                {"model": model, "input": text},
                timeout=30.0,
                headers=self.headers,
            )
        except Exception:
            return None
        embeddings = result.get("embeddings")
        if not isinstance(embeddings, list) or not embeddings:
            return None
        vec = embeddings[0]
        if not isinstance(vec, list) or not vec:
            return None
        return vec
