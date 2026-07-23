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

from pydantic import BaseModel

from .provider import Message, ModelInfo, ModelStatus
from .retry import RETRY_BACKOFF_SECS, next_seed

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


_MODEL_LIST_CACHE = _TTLLRUCache(maxsize=32, ttl_seconds=20.0)
_CHAT_RESPONSE_CACHE = _TTLLRUCache(maxsize=64, ttl_seconds=None)


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
    ) -> str:
        payload_messages = [m.model_dump() for m in messages]
        total_attempts = max(0, min(int(max_retries), 5)) + 1
        response_text = ""
        incomplete = False

        for attempt in range(1, total_attempts + 1):
            attempt_options = dict(options) if options else {}
            if attempt > 1:
                attempt_options["seed"] = next_seed(options, attempt)

            payload: dict = {
                "model": model,
                "messages": payload_messages,
                "stream": False,
            }
            if attempt_options:
                payload["options"] = attempt_options

            cache_key = _cache_key(
                "chat",
                self.host,
                self.headers or {},
                model,
                payload_messages,
                attempt_options,
            )
            cached, hit = _CHAT_RESPONSE_CACHE.get(cache_key)
            if hit:
                return cached

            result = await _post_json(
                f"{self.host}/api/chat",
                payload,
                timeout=timeout_secs,
                headers=self.headers,
            )
            response_text = result.get("message", {}).get("content", "")
            if response_text.strip():
                _CHAT_RESPONSE_CACHE.set(cache_key, response_text)
                return response_text

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
    ) -> BaseModel:
        from .chat import chat_structured as _chat_structured_impl

        payload_messages = [m.model_dump() for m in messages]
        cache_key = _cache_key(
            "chat_structured",
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
