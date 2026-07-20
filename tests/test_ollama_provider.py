"""
Tests for comfydv._llm.ollama_provider.OllamaProvider — the Ollama-specific
LLMProvider implementation. Mocks at the module's own _post_json/_get_json
seam, mirroring test_ollama.py's established convention.

Node-contract/delegation tests (does ChatCompletion call client.chat(...)
correctly) live in tests/test_ollama.py against a _FakeProvider double —
this file only tests OllamaProvider's actual Ollama-wire-protocol behavior.

BDD coverage:
  ../specs/007-llm-provider-abstraction/features/us1_connect_and_chat.feature
  ../specs/007-llm-provider-abstraction/features/us3_model_lifecycle.feature
"""

import asyncio

import pytest

import comfydv._llm.ollama_provider as provider_mod
from comfydv._llm.ollama_provider import OllamaProvider, _run_async
from comfydv._llm.provider import Message, ModelStatus


@pytest.fixture(autouse=True)
def _clear_provider_caches():
    provider_mod._MODEL_LIST_CACHE.clear()
    provider_mod._CHAT_RESPONSE_CACHE.clear()
    yield
    provider_mod._MODEL_LIST_CACHE.clear()
    provider_mod._CHAT_RESPONSE_CACHE.clear()


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


def test_list_models_marks_running_models_loaded(monkeypatch):
    async def fake_get(url, *, timeout=5.0, headers=None):
        if url.endswith("/api/tags"):
            return {
                "models": [
                    {"name": "a:latest", "size": 100},
                    {"name": "b:latest", "size": 200},
                ]
            }
        assert url.endswith("/api/ps")
        return {"models": [{"name": "a:latest"}]}

    monkeypatch.setattr(provider_mod, "_get_json", fake_get)

    models = _run_async(OllamaProvider("http://localhost:11434").list_models())

    by_name = {m.name: m for m in models}
    assert by_name["a:latest"].status == ModelStatus.LOADED
    assert by_name["a:latest"].size == 100
    assert by_name["b:latest"].status == ModelStatus.UNLOADED
    assert by_name["b:latest"].size == 200


def test_list_models_never_emits_sleeping_or_downloading(monkeypatch):
    async def fake_get(url, *, timeout=5.0, headers=None):
        if url.endswith("/api/tags"):
            return {"models": [{"name": "a:latest"}]}
        return {"models": []}

    monkeypatch.setattr(provider_mod, "_get_json", fake_get)
    models = _run_async(OllamaProvider("http://localhost:11434").list_models())

    assert all(m.status in (ModelStatus.LOADED, ModelStatus.UNLOADED) for m in models)


def test_list_models_unreachable_returns_empty(monkeypatch):
    async def fake_get(url, *, timeout=5.0, headers=None):
        raise ConnectionError("no route to host")

    monkeypatch.setattr(provider_mod, "_get_json", fake_get)
    models = _run_async(OllamaProvider("http://localhost:19999").list_models())

    assert models == []


def test_list_models_cached_second_call(monkeypatch):
    calls = {"n": 0}

    async def fake_get(url, *, timeout=5.0, headers=None):
        calls["n"] += 1
        if url.endswith("/api/tags"):
            return {"models": [{"name": "a:latest"}]}
        return {"models": []}

    monkeypatch.setattr(provider_mod, "_get_json", fake_get)
    provider = OllamaProvider("http://localhost:11434")
    _run_async(provider.list_models())
    calls_after_first = calls["n"]
    _run_async(provider.list_models())

    assert calls["n"] == calls_after_first  # second call served from cache


# ---------------------------------------------------------------------------
# load_model / unload_model
# ---------------------------------------------------------------------------


def test_load_model_uses_api_generate_keep_alive_negative_one(monkeypatch):
    captured = {}

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        captured["url"] = url
        captured["payload"] = payload
        return {}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    _run_async(OllamaProvider("http://localhost:11434").load_model("llama3"))

    assert captured["url"].endswith("/api/generate")
    assert captured["payload"]["keep_alive"] == -1
    assert isinstance(captured["payload"]["keep_alive"], int)


def test_unload_model_uses_api_generate_keep_alive_zero(monkeypatch):
    captured = {}

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        captured["url"] = url
        captured["payload"] = payload
        return {}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    _run_async(OllamaProvider("http://localhost:11434").unload_model("llama3"))

    assert captured["url"].endswith("/api/generate")
    assert captured["payload"]["keep_alive"] == 0
    assert isinstance(captured["payload"]["keep_alive"], int)


def test_load_model_empty_raises_before_network(monkeypatch):
    def fail_post(*a, **k):
        raise AssertionError("must not call _post_json for an empty model name")

    monkeypatch.setattr(provider_mod, "_post_json", fail_post)
    with pytest.raises(ValueError, match="cannot be empty"):
        _run_async(OllamaProvider("http://localhost:11434").load_model(""))


def test_unload_model_empty_raises_before_network(monkeypatch):
    def fail_post(*a, **k):
        raise AssertionError("must not call _post_json for an empty model name")

    monkeypatch.setattr(provider_mod, "_post_json", fail_post)
    with pytest.raises(ValueError, match="cannot be empty"):
        _run_async(OllamaProvider("http://localhost:11434").unload_model("   "))


def test_load_model_forwards_headers(monkeypatch):
    captured = {}

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        captured["headers"] = headers
        return {}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    provider = OllamaProvider(
        "http://localhost:11434", headers={"Authorization": "Bearer x"}
    )
    _run_async(provider.load_model("llama3"))

    assert captured["headers"] == {"Authorization": "Bearer x"}


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------


def test_chat_uses_api_chat_and_returns_content(monkeypatch):
    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        assert url.endswith("/api/chat")
        return {"message": {"content": "hello there"}}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    result = _run_async(
        OllamaProvider("http://localhost:11434").chat(
            "llama3", [Message(role="user", content="hi")]
        )
    )

    assert result == "hello there"


def test_chat_second_identical_call_is_cached(monkeypatch):
    calls = {"n": 0}

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        calls["n"] += 1
        return {"message": {"content": "cached response"}}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    provider = OllamaProvider("http://localhost:11434")
    messages = [Message(role="user", content="hi")]

    r1 = _run_async(provider.chat("llama3", messages))
    r2 = _run_async(provider.chat("llama3", messages))

    assert r1 == r2 == "cached response"
    assert calls["n"] == 1


def test_chat_different_client_headers_not_cached(monkeypatch):
    calls = {"n": 0}

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        calls["n"] += 1
        return {"message": {"content": f"response for {headers}"}}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    messages = [Message(role="user", content="hi")]

    _run_async(OllamaProvider("http://localhost:11434").chat("llama3", messages))
    _run_async(
        OllamaProvider("http://localhost:11434", headers={"X": "1"}).chat(
            "llama3", messages
        )
    )

    assert calls["n"] == 2


def test_chat_timeout_forwarded(monkeypatch):
    captured = {}

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        captured["timeout"] = timeout
        return {"message": {"content": "ok"}}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    _run_async(
        OllamaProvider("http://localhost:11434").chat(
            "llama3", [Message(role="user", content="hi")], timeout_secs=600.0
        )
    )

    assert captured["timeout"] == 600.0


# ---------------------------------------------------------------------------
# chat — retry-on-blank-output (live-verified: a freshly-loaded model's first
# response is sometimes blank on a fresh runpod, then normal afterwards)
# ---------------------------------------------------------------------------


async def _fake_sleep(_secs):
    """No-op stand-in for asyncio.sleep — keeps retry tests instant."""


def test_chat_retries_on_blank_response_and_returns_second_attempt(monkeypatch):
    calls = []

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        calls.append(payload)
        if len(calls) == 1:
            return {"message": {"content": ""}}
        return {"message": {"content": "real answer"}}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    monkeypatch.setattr(provider_mod.asyncio, "sleep", _fake_sleep)

    result = _run_async(
        OllamaProvider("http://localhost:11434").chat(
            "llama3", [Message(role="user", content="hi")]
        )
    )

    assert result == "real answer"
    assert len(calls) == 2


def test_chat_retry_injects_incrementing_seed_when_none_pinned(monkeypatch):
    calls = []

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        calls.append(payload)
        if len(calls) < 3:
            return {"message": {"content": ""}}
        return {"message": {"content": "ok"}}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    monkeypatch.setattr(provider_mod.asyncio, "sleep", _fake_sleep)

    _run_async(
        OllamaProvider("http://localhost:11434").chat(
            "llama3", [Message(role="user", content="hi")], max_retries=2
        )
    )

    assert "seed" not in calls[0].get("options", {})
    assert calls[1]["options"]["seed"] == 1
    assert calls[2]["options"]["seed"] == 2


def test_chat_retry_seed_starts_from_pinned_base(monkeypatch):
    calls = []

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        calls.append(payload)
        if len(calls) == 1:
            return {"message": {"content": ""}}
        return {"message": {"content": "ok"}}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    monkeypatch.setattr(provider_mod.asyncio, "sleep", _fake_sleep)

    _run_async(
        OllamaProvider("http://localhost:11434").chat(
            "llama3",
            [Message(role="user", content="hi")],
            options={"seed": 42},
        )
    )

    assert calls[0]["options"]["seed"] == 42  # attempt 1 untouched
    assert calls[1]["options"]["seed"] == 43  # attempt 2 = base + 1


def test_chat_exhausted_retries_returns_blank_without_raising(monkeypatch):
    calls = []

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        calls.append(payload)
        return {"message": {"content": ""}}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    monkeypatch.setattr(provider_mod.asyncio, "sleep", _fake_sleep)

    result = _run_async(
        OllamaProvider("http://localhost:11434").chat(
            "llama3", [Message(role="user", content="hi")], max_retries=2
        )
    )

    assert result == ""
    assert len(calls) == 3  # original + 2 retries, per max_retries=2


def test_chat_blank_response_is_not_cached(monkeypatch):
    """A blank final result must not poison the cache — the next queue run
    should try the real backend again, not replay the blank forever (the
    cache has no TTL)."""
    calls = {"n": 0}

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        calls["n"] += 1
        return {"message": {"content": ""}}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    monkeypatch.setattr(provider_mod.asyncio, "sleep", _fake_sleep)

    provider = OllamaProvider("http://localhost:11434")
    messages = [Message(role="user", content="hi")]
    _run_async(provider.chat(model="llama3", messages=messages, max_retries=0))
    calls_after_first_run = calls["n"]
    _run_async(provider.chat(model="llama3", messages=messages, max_retries=0))

    assert calls["n"] > calls_after_first_run  # second run hit the network again


def test_chat_no_retry_needed_does_not_sleep(monkeypatch):
    sleep_calls = []

    async def fake_sleep(secs):
        sleep_calls.append(secs)

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        return {"message": {"content": "first try works"}}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    monkeypatch.setattr(provider_mod.asyncio, "sleep", fake_sleep)

    _run_async(
        OllamaProvider("http://localhost:11434").chat(
            "llama3", [Message(role="user", content="hi")]
        )
    )

    assert sleep_calls == []


# ---------------------------------------------------------------------------
# chat_structured
# ---------------------------------------------------------------------------


def test_chat_structured_builds_v1_base_url_and_delegates(monkeypatch):
    from pydantic import BaseModel

    class Widget(BaseModel):
        name: str

    captured = {}

    async def fake_chat_structured(**kwargs):
        captured.update(kwargs)
        return Widget(name="x")

    monkeypatch.setattr(
        "comfydv._llm.chat.chat_structured",
        fake_chat_structured,
    )

    result = _run_async(
        OllamaProvider("http://localhost:11434").chat_structured(
            "llama3", [Message(role="user", content="hi")], Widget
        )
    )

    assert result == Widget(name="x")
    assert captured["base_url"] == "http://localhost:11434/v1"
    assert captured["model"] == "llama3"


def test_chat_structured_forwards_options(monkeypatch):
    """Regression guard: options must reach the shared chat_structured()
    helper, not just the cache key — see specs/007-llm-provider-abstraction
    beacon-reviewer finding."""
    from pydantic import BaseModel

    class Widget(BaseModel):
        name: str

    captured = {}

    async def fake_chat_structured(**kwargs):
        captured.update(kwargs)
        return Widget(name="x")

    monkeypatch.setattr("comfydv._llm.chat.chat_structured", fake_chat_structured)

    _run_async(
        OllamaProvider("http://localhost:11434").chat_structured(
            "llama3",
            [Message(role="user", content="hi")],
            Widget,
            options={"temperature": 0.0, "seed": 42},
        )
    )

    assert captured["options"] == {"temperature": 0.0, "seed": 42}


def test_chat_structured_caches_after_successful_validation(monkeypatch):
    from pydantic import BaseModel

    class Widget(BaseModel):
        name: str

    calls = {"n": 0}

    async def fake_chat_structured(**kwargs):
        calls["n"] += 1
        return Widget(name="cached")

    monkeypatch.setattr("comfydv._llm.chat.chat_structured", fake_chat_structured)

    provider = OllamaProvider("http://localhost:11434")
    messages = [Message(role="user", content="hi")]

    r1 = _run_async(provider.chat_structured("llama3", messages, Widget))
    r2 = _run_async(provider.chat_structured("llama3", messages, Widget))

    assert r1 == r2 == Widget(name="cached")
    assert calls["n"] == 1


# ---------------------------------------------------------------------------
# _run_async — regression coverage for a bug found running the real
# docker-compose ComfyUI harness (not caught by any prior test, and not
# reproducible under pytest — see below). ComfyUI's actual async execution
# engine runs node functions synchronously *inside* an already-running event
# loop. The old implementation tried `asyncio.get_running_loop()` first and
# only spun up an isolated worker thread if that succeeded — under real
# ComfyUI (Python 3.13), that check sometimes raised anyway, falling through
# to a direct `asyncio.run(coro)` call on the *current* thread — the one
# thread guaranteed to already have a loop running — reproducing "asyncio.run()
# cannot be called from a running event loop" exactly, every time
# chat_structured() was called.
#
# Honest caveat (raised by beacon-reviewer, confirmed by reconstructing the
# old code and running it against these tests): under CPython/pytest,
# asyncio.get_running_loop() inside asyncio.run(outer()) never spuriously
# raises, so the *old, buggy* implementation also takes the safe
# worker-thread branch here and these tests pass against it too. They do not
# reproduce the actual reported bug — only the live end-to-end run against
# real ComfyUI did that. What these tests do lock in: the documented
# contract ("calling _run_async from within a running loop must work and
# must propagate exceptions"), so a regression to a naive
# `asyncio.run(coro)`-with-no-thread implementation (which *does* fail here)
# gets caught immediately.
# ---------------------------------------------------------------------------


def test_run_async_works_with_no_ambient_loop():
    async def coro():
        return "ok"

    assert _run_async(coro()) == "ok"


def test_run_async_works_when_called_from_within_a_running_loop():
    """The actual shape of a real ComfyUI node call: a synchronous function
    invoked from code that is itself already executing inside
    asyncio.run(). Must not raise "asyncio.run() cannot be called from a
    running event loop"."""

    async def inner_coro():
        return "from inside a running loop"

    def sync_node_function():
        # This is exactly what comfydv.ollama's chat() does: a plain sync
        # function calling _run_async(some_coroutine()).
        return _run_async(inner_coro())

    async def outer():
        # Mirrors ComfyUI's execution.py calling `result = f(**inputs)`
        # synchronously from within its own already-running event loop.
        return sync_node_function()

    result = asyncio.run(outer())
    assert result == "from inside a running loop"


def test_run_async_propagates_exceptions_from_within_a_running_loop():
    async def failing_coro():
        raise ValueError("boom")

    async def outer():
        return _run_async(failing_coro())

    with pytest.raises(ValueError, match="boom"):
        asyncio.run(outer())
