"""
Tests for comfydv._llm.llamacpp_provider.LlamaCppProvider — mirrors
test_ollama_provider.py's structure exactly (ADR-007's parallel-
implementation pattern). Mocks at the provider's own _post_json/_get_json
seam.

BDD coverage:
  ../specs/008-llamacpp-integration/features/us1_connect_and_chat.feature
  ../specs/008-llamacpp-integration/features/us2_structured_output.feature
  ../specs/008-llamacpp-integration/features/us3_model_lifecycle.feature
"""

import pytest

import comfydv._llm.llamacpp_provider as provider_mod
from comfydv._llm.llamacpp_provider import LlamaCppProvider
from comfydv._llm.ollama_provider import _run_async
from comfydv._llm.provider import Message, ModelStatus


@pytest.fixture(autouse=True)
def _clear_provider_caches():
    provider_mod._MODEL_LIST_CACHE.clear()
    provider_mod._CHAT_RESPONSE_CACHE.clear()
    yield
    provider_mod._MODEL_LIST_CACHE.clear()
    provider_mod._CHAT_RESPONSE_CACHE.clear()


# ---------------------------------------------------------------------------
# list_models — the "id" field name and nested "status.value" are the two
# details research.md flagged as easy to get wrong by assumption.
# ---------------------------------------------------------------------------


def test_list_models_maps_id_field_to_name(monkeypatch):
    async def fake_get(url, *, timeout=5.0, headers=None):
        return {"data": [{"id": "gemma-3-4b:Q4_K_M", "status": {"value": "loaded"}}]}

    monkeypatch.setattr(provider_mod, "_get_json", fake_get)
    (model,) = _run_async(LlamaCppProvider("http://localhost:8080").list_models())

    assert model.name == "gemma-3-4b:Q4_K_M"


def test_list_models_reads_nested_status_value(monkeypatch):
    async def fake_get(url, *, timeout=5.0, headers=None):
        return {
            "data": [
                {"id": "a", "status": {"value": "sleeping"}},
                {"id": "b", "status": {"value": "downloading", "progress": {}}},
            ]
        }

    monkeypatch.setattr(provider_mod, "_get_json", fake_get)
    models = _run_async(LlamaCppProvider("http://localhost:8080").list_models())

    by_name = {m.name: m for m in models}
    assert by_name["a"].status == ModelStatus.SLEEPING
    assert by_name["b"].status == ModelStatus.DOWNLOADING


def test_list_models_no_normalization_needed_full_vocabulary(monkeypatch):
    """Unlike OllamaProvider, llama.cpp's status vocabulary is exactly
    ModelStatus's full set — every value should pass through untouched."""

    async def fake_get(url, *, timeout=5.0, headers=None):
        return {
            "data": [
                {"id": v, "status": {"value": v}}
                for v in ["unloaded", "loading", "loaded", "sleeping", "downloading"]
            ]
        }

    monkeypatch.setattr(provider_mod, "_get_json", fake_get)
    models = _run_async(LlamaCppProvider("http://localhost:8080").list_models())

    assert {m.status for m in models} == set(ModelStatus)


def test_list_models_skips_unrecognized_status(monkeypatch):
    async def fake_get(url, *, timeout=5.0, headers=None):
        return {
            "data": [
                {"id": "crashed", "status": {"value": "failed", "exit_code": 1}},
                {"id": "ok", "status": {"value": "loaded"}},
            ]
        }

    monkeypatch.setattr(provider_mod, "_get_json", fake_get)
    models = _run_async(LlamaCppProvider("http://localhost:8080").list_models())

    assert [m.name for m in models] == ["ok"]


def test_list_models_unreachable_returns_empty(monkeypatch):
    async def fake_get(url, *, timeout=5.0, headers=None):
        raise ConnectionError("no route to host")

    monkeypatch.setattr(provider_mod, "_get_json", fake_get)
    models = _run_async(LlamaCppProvider("http://localhost:19999").list_models())

    assert models == []


def test_list_models_non_router_mode_raises_clear_error(monkeypatch):
    """FR-006: a llama-server that IS reachable but wasn't launched with
    --models-dir/--models-preset answers GET /models with an HTTP error
    (the endpoint doesn't exist outside router mode). That must surface as
    a specific, actionable error — not silently degrade to an empty list,
    which would be indistinguishable from "server has no models"."""

    async def fake_get(url, *, timeout=5.0, headers=None):
        raise RuntimeError("Server returned HTTP 404 for http://x/models: not found")

    monkeypatch.setattr(provider_mod, "_get_json", fake_get)

    with pytest.raises(RuntimeError, match="router mode"):
        _run_async(LlamaCppProvider("http://localhost:8080").list_models())


def test_list_models_cached_second_call(monkeypatch):
    calls = {"n": 0}

    async def fake_get(url, *, timeout=5.0, headers=None):
        calls["n"] += 1
        return {"data": [{"id": "a", "status": {"value": "loaded"}}]}

    monkeypatch.setattr(provider_mod, "_get_json", fake_get)
    provider = LlamaCppProvider("http://localhost:8080")
    _run_async(provider.list_models())
    _run_async(provider.list_models())

    assert calls["n"] == 1


# ---------------------------------------------------------------------------
# load_model / unload_model
# ---------------------------------------------------------------------------


def test_load_model_posts_to_models_load_with_model_field(monkeypatch):
    captured = {}

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        captured["url"] = url
        captured["payload"] = payload
        return {"success": True}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    _run_async(LlamaCppProvider("http://localhost:8080").load_model("gemma-3-4b"))

    assert captured["url"] == "http://localhost:8080/models/load"
    assert captured["payload"] == {"model": "gemma-3-4b"}


def test_unload_model_posts_to_models_unload_with_model_field(monkeypatch):
    captured = {}

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        captured["url"] = url
        captured["payload"] = payload
        return {"success": True}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    _run_async(LlamaCppProvider("http://localhost:8080").unload_model("gemma-3-4b"))

    assert captured["url"] == "http://localhost:8080/models/unload"
    assert captured["payload"] == {"model": "gemma-3-4b"}


def test_load_model_already_running_is_idempotent(monkeypatch):
    """Confirmed live: router mode's /models/load is NOT idempotent at the
    wire level — it 400s "model is already running" rather than returning
    {"success": true}. The LLMProvider protocol requires load_model() to be
    idempotent, so LlamaCppProvider must absorb this itself."""
    calls = []

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        calls.append((url, payload))
        raise RuntimeError(
            "Server returned HTTP 400 for "
            f'{url}: {{"error":{{"code":400,"message":"model is already '
            'running","type":"invalid_request_error"}}}}'
        )

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    _run_async(LlamaCppProvider("http://localhost:8080").load_model("gemma-3-4b"))

    # The absence of a raised exception is only meaningful if the request
    # actually happened and hit the "already running" branch — assert that
    # directly rather than trusting silence alone.
    assert calls == [("http://localhost:8080/models/load", {"model": "gemma-3-4b"})]


def test_load_model_other_http_error_still_raises(monkeypatch):
    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        raise RuntimeError(f"Server returned HTTP 500 for {url}: internal error")

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    with pytest.raises(RuntimeError, match="500"):
        _run_async(LlamaCppProvider("http://localhost:8080").load_model("gemma-3-4b"))


def test_unload_model_not_running_is_idempotent(monkeypatch):
    """Mirror of the load_model case, confirmed live: /models/unload 400s
    "model is not running" on an already-unloaded model."""
    calls = []

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        calls.append((url, payload))
        raise RuntimeError(
            "Server returned HTTP 400 for "
            f'{url}: {{"error":{{"code":400,"message":"model is not '
            'running","type":"invalid_request_error"}}}}'
        )

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    _run_async(LlamaCppProvider("http://localhost:8080").unload_model("gemma-3-4b"))

    assert calls == [("http://localhost:8080/models/unload", {"model": "gemma-3-4b"})]


def test_unload_model_other_http_error_still_raises(monkeypatch):
    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        raise RuntimeError(f"Server returned HTTP 500 for {url}: internal error")

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    with pytest.raises(RuntimeError, match="500"):
        _run_async(LlamaCppProvider("http://localhost:8080").unload_model("gemma-3-4b"))


def test_load_model_empty_raises_before_network(monkeypatch):
    def fail_post(*a, **k):
        raise AssertionError("must not call _post_json for an empty model name")

    monkeypatch.setattr(provider_mod, "_post_json", fail_post)
    with pytest.raises(ValueError, match="cannot be empty"):
        _run_async(LlamaCppProvider("http://localhost:8080").load_model(""))


def test_unload_model_empty_raises_before_network(monkeypatch):
    def fail_post(*a, **k):
        raise AssertionError("must not call _post_json for an empty model name")

    monkeypatch.setattr(provider_mod, "_post_json", fail_post)
    with pytest.raises(ValueError, match="cannot be empty"):
        _run_async(LlamaCppProvider("http://localhost:8080").unload_model("  "))


# ---------------------------------------------------------------------------
# chat — OpenAI response shape (choices[0].message.content), not Ollama's
# native shape
# ---------------------------------------------------------------------------


def test_chat_posts_to_v1_chat_completions_and_parses_openai_shape(monkeypatch):
    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        assert url == "http://localhost:8080/v1/chat/completions"
        return {"choices": [{"message": {"role": "assistant", "content": "hello"}}]}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    result = _run_async(
        LlamaCppProvider("http://localhost:8080").chat(
            "gemma-3-4b", [Message(role="user", content="hi")]
        )
    )

    assert result == "hello"


def test_chat_no_choices_returns_empty_string(monkeypatch):
    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        return {"choices": []}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    result = _run_async(
        LlamaCppProvider("http://localhost:8080").chat(
            "gemma-3-4b", [Message(role="user", content="hi")]
        )
    )

    assert result == ""


def test_chat_second_identical_call_is_cached(monkeypatch):
    calls = {"n": 0}

    async def fake_post(url, payload, *, timeout=120.0, headers=None):
        calls["n"] += 1
        return {"choices": [{"message": {"content": "cached"}}]}

    monkeypatch.setattr(provider_mod, "_post_json", fake_post)
    provider = LlamaCppProvider("http://localhost:8080")
    messages = [Message(role="user", content="hi")]

    r1 = _run_async(provider.chat("m", messages))
    r2 = _run_async(provider.chat("m", messages))

    assert r1 == r2 == "cached"
    assert calls["n"] == 1


# ---------------------------------------------------------------------------
# chat_structured — zero new logic, delegates to the shared helper unchanged
# ---------------------------------------------------------------------------


def test_chat_structured_builds_v1_base_url_and_delegates(monkeypatch):
    from pydantic import BaseModel

    class Widget(BaseModel):
        name: str

    captured = {}

    async def fake_chat_structured(**kwargs):
        captured.update(kwargs)
        return Widget(name="x")

    monkeypatch.setattr("comfydv._llm.chat.chat_structured", fake_chat_structured)

    result = _run_async(
        LlamaCppProvider("http://localhost:8080").chat_structured(
            "gemma-3-4b", [Message(role="user", content="hi")], Widget
        )
    )

    assert result == Widget(name="x")
    assert captured["base_url"] == "http://localhost:8080/v1"
    assert captured["model"] == "gemma-3-4b"


def test_chat_structured_forwards_options(monkeypatch):
    from pydantic import BaseModel

    class Widget(BaseModel):
        name: str

    captured = {}

    async def fake_chat_structured(**kwargs):
        captured.update(kwargs)
        return Widget(name="x")

    monkeypatch.setattr("comfydv._llm.chat.chat_structured", fake_chat_structured)

    _run_async(
        LlamaCppProvider("http://localhost:8080").chat_structured(
            "gemma-3-4b",
            [Message(role="user", content="hi")],
            Widget,
            options={"temperature": 0.0},
        )
    )

    assert captured["options"] == {"temperature": 0.0}
