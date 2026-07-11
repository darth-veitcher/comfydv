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
