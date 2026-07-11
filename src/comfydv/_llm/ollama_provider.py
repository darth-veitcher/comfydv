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
    """Run an async coroutine synchronously, safe inside a running event loop."""
    try:
        asyncio.get_running_loop()
        # Called from within a running loop (e.g. ComfyUI's async executor).
        # Spin up a worker thread with its own loop to avoid "loop already running".
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


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


class OllamaProvider:
    """LLMProvider implementation backed by Ollama's REST API.

    Host and headers are captured once at construction — every method
    reuses them, matching the ADR-005 config-node pattern (one
    ``OllamaClient`` node's output is one ``OllamaProvider`` instance).

    Method bodies land incrementally across
    specs/007-llm-provider-abstraction/tasks.md's user-story phases; see
    that file for current status.
    """

    def __init__(self, host: str, headers: dict | None = None):
        self.host = host
        self.headers = dict(headers) if headers else None
