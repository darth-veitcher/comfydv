"""
Tests for comfydv.ollama — 14-node Ollama integration.

Test layers:
  Unit (no marker)             — pure Python, no live services
  Integration (-m integration) — requires live Ollama at localhost:11434
  System (-m system)           — requires full docker-compose harness

BDD coverage:
  features/us1_ollama_connection.feature
  features/us2_model_selection.feature
  features/us3_model_lifecycle.feature
  features/us4_chat_completion.feature
  features/us5_composable_options.feature
  features/us6_history_inspection.feature
"""

import asyncio
import json

import pytest

from comfydv.ollama import (
    OllamaChatCompletion,
    OllamaClient,
    OllamaClientType,
    OllamaDebugHistory,
    OllamaHeaderBasicAuth,
    OllamaHeaderBearerToken,
    OllamaHeaderCustom,
    OllamaHistoryLength,
    OllamaLoadModel,
    OllamaModelSelector,
    OllamaOptionExtraBody,
    OllamaOptionMaxTokens,
    OllamaOptionRepeatPenalty,
    OllamaOptionSeed,
    OllamaOptionTemperature,
    OllamaOptionTopK,
    OllamaOptionTopP,
    OllamaUnloadModel,
    _MODEL_LIST_CACHE,
    _fetch_models,
    _post_json,
    _run_async,
)

# ---------------------------------------------------------------------------
# Infrastructure tests (Issues 1–3: event loop safety, HTTP errors, timeout)
# ---------------------------------------------------------------------------


class TestInfrastructure:
    # ---- Issue 1: _run_async event loop safety --------------------------------

    def test_run_async_works_from_running_loop(self):
        """Issue 1: _run_async must work when called from inside a running event loop.

        ComfyUI drives nodes inside its own asyncio event loop.  Calling
        _run_async (which currently spawns a new loop) from within that context
        raises "Cannot run the event loop while another loop is running".
        """

        async def _simple():
            return 42

        async def _caller():
            # Simulates a synchronous ComfyUI node method being invoked from
            # within the server's async event loop.
            return _run_async(_simple())

        result = asyncio.run(_caller())
        assert result == 42

    # ---- Issue 2: _post_json HTTP error checking ------------------------------

    def test_post_json_raises_on_http_4xx(self, monkeypatch):
        """Issue 2: _post_json must raise RuntimeError on 4xx responses.

        Currently it silently returns the response body as a dict.
        """
        import aiohttp

        class FakeResponse:
            status = 422

            async def text(self):
                return "Unprocessable"

            async def json(self):
                return {"error": "Unprocessable"}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        class FakeSession:
            def post(self, *args, **kwargs):
                return FakeResponse()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        monkeypatch.setattr(aiohttp, "ClientSession", lambda: FakeSession())

        with pytest.raises(RuntimeError, match="HTTP 422"):
            _run_async(_post_json("http://localhost/test", {}))

    def test_post_json_raises_on_http_5xx(self, monkeypatch):
        """Issue 2: _post_json must raise RuntimeError on 5xx responses.

        Currently it silently returns the response body as a dict.
        """
        import aiohttp

        class FakeResponse:
            status = 500

            async def text(self):
                return "Internal Server Error"

            async def json(self):
                return {"error": "Internal Server Error"}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        class FakeSession:
            def post(self, *args, **kwargs):
                return FakeResponse()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        monkeypatch.setattr(aiohttp, "ClientSession", lambda: FakeSession())

        with pytest.raises(RuntimeError, match="HTTP 500"):
            _run_async(_post_json("http://localhost/test", {}))

    # ---- Issue 3: _post_json timeout parameter --------------------------------

    def test_post_json_timeout_forwarded(self, monkeypatch):
        """Issue 3: _post_json must accept a timeout kwarg and forward it to aiohttp.

        Currently _post_json has no timeout parameter, so the call raises TypeError.
        """
        import aiohttp

        captured = {}

        class FakeResponse:
            status = 200

            async def text(self):
                return "{}"

            async def json(self):
                return {}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        class FakeSession:
            def post(self, url, *, json=None, timeout=None, headers=None):
                captured["timeout"] = timeout
                return FakeResponse()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        monkeypatch.setattr(aiohttp, "ClientSession", lambda: FakeSession())

        _run_async(_post_json("http://localhost/test", {}, timeout=42.0))
        assert captured.get("timeout") is not None, (
            "_post_json did not forward a timeout object to aiohttp"
        )
        assert captured["timeout"].total == 42.0, (
            f"Expected ClientTimeout(total=42.0) but got total={captured['timeout'].total}"
        )


# ---------------------------------------------------------------------------
# US1 — Ollama Connection  (us1_ollama_connection.feature)
# ---------------------------------------------------------------------------


class TestUS1OllamaConnection:
    def test_client_outputs_ollama_client_type(self):
        """Scenario: Default host connects to local Ollama."""
        (client,) = OllamaClient().create_client("http://localhost:11434")
        assert isinstance(client, OllamaClientType)
        assert client == "http://localhost:11434"

    def test_client_custom_host_is_preserved(self):
        """Scenario: Host change causes widgets to refresh."""
        (client,) = OllamaClient().create_client("http://myserver:11434")
        assert client == "http://myserver:11434"

    @pytest.mark.integration
    def test_unreachable_host_raises_named_error(self, skip_if_no_ollama):
        """Scenario: Unreachable host surfaces a named error."""
        with pytest.raises(RuntimeError, match="Cannot reach Ollama"):
            OllamaLoadModel().load_model(
                client="http://localhost:19999", model="embeddinggemma:latest"
            )


# ---------------------------------------------------------------------------
# US2 — Model Selection  (us2_model_selection.feature)
# ---------------------------------------------------------------------------


class TestUS2ModelSelection:
    @pytest.mark.integration
    def test_fetch_models_returns_list(self, ollama_host, skip_if_no_ollama):
        """Scenario: Dropdown lists all installed models."""
        models = _run_async(_fetch_models(ollama_host))
        assert isinstance(models, list)
        assert len(models) > 0
        assert all(isinstance(m, str) for m in models)

    @pytest.mark.integration
    def test_model_selector_output_is_exact_name(self, ollama_host, skip_if_no_ollama):
        """Scenario: Selected model name is the node output."""
        models = _run_async(_fetch_models(ollama_host))
        model = models[0]
        (result,) = OllamaModelSelector().select_model(client=ollama_host, model=model)
        assert result == model

    def test_model_selector_input_types_uses_combo(self):
        """Scenario: OllamaModelSelector shows a dropdown (not a text box)."""
        input_types = OllamaModelSelector.INPUT_TYPES()
        model_input = input_types["required"]["model"]
        assert isinstance(model_input[0], list), (
            "model input must be a COMBO (list), not STRING"
        )

    def test_fetch_models_unreachable_returns_empty(self):
        """Scenario: Unreachable host returns empty list (no crash)."""
        models = _run_async(_fetch_models("http://localhost:19999"))
        assert models == []


# ---------------------------------------------------------------------------
# US3 — Model Lifecycle  (us3_model_lifecycle.feature)
# ---------------------------------------------------------------------------


class TestUS3ModelLifecycle:
    def test_load_model_input_types_uses_combo(self):
        """Scenario: Load Model shows live dropdown (fixes Issue #1)."""
        input_types = OllamaLoadModel.INPUT_TYPES()
        model_input = input_types["required"]["model"]
        assert isinstance(model_input[0], list), (
            "OllamaLoadModel model input must be a COMBO (list) — Issue #1 fix"
        )

    def test_empty_model_raises_before_http(self):
        """Scenario: Empty model name is rejected before contacting Ollama."""
        with pytest.raises(ValueError, match="cannot be empty"):
            OllamaLoadModel().load_model(client="http://localhost:11434", model="")

    def test_empty_model_whitespace_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            OllamaLoadModel().load_model(client="http://localhost:11434", model="   ")

    def test_unload_empty_model_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            OllamaUnloadModel().unload_model(client="http://localhost:11434", model="")

    # ---- Issue 4: Load/Unload API endpoint ------------------------------------

    def test_load_uses_api_generate_not_api_show(self, monkeypatch):
        """Issue 4: load_model should POST to /api/generate, not /api/show."""
        captured = {}

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            captured["url"] = url
            return {}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        OllamaLoadModel().load_model(
            client="http://localhost:11434", model="test-model"
        )

        assert captured.get("url", "").endswith("/api/generate"), (
            f"Expected URL ending in /api/generate but got: {captured.get('url')}"
        )

    def test_unload_uses_api_generate_not_api_show(self, monkeypatch):
        """Issue 4: unload_model should POST to /api/generate, not /api/show."""
        captured = {}

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            captured["url"] = url
            return {}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        OllamaUnloadModel().unload_model(
            client="http://localhost:11434", model="test-model"
        )

        assert captured.get("url", "").endswith("/api/generate"), (
            f"Expected URL ending in /api/generate but got: {captured.get('url')}"
        )

    # ---- Issue 5: keep_alive integer type -------------------------------------

    def test_load_keep_alive_is_integer_negative_one(self, monkeypatch):
        """Issue 5: load_model must send keep_alive as integer -1, not string '-1'."""
        captured = {}

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            captured["payload"] = payload
            return {}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        OllamaLoadModel().load_model(
            client="http://localhost:11434", model="test-model"
        )

        payload = captured.get("payload", {})
        assert payload.get("keep_alive") == -1, (
            f"Expected keep_alive=-1 (int) but got {payload.get('keep_alive')!r}"
        )
        assert isinstance(payload.get("keep_alive"), int), (
            f"keep_alive must be int, got {type(payload.get('keep_alive'))}"
        )

    def test_unload_keep_alive_is_integer_zero(self, monkeypatch):
        """Issue 5: unload_model must send keep_alive as integer 0."""
        captured = {}

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            captured["payload"] = payload
            return {}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        OllamaUnloadModel().unload_model(
            client="http://localhost:11434", model="test-model"
        )

        payload = captured.get("payload", {})
        assert payload.get("keep_alive") == 0, (
            f"Expected keep_alive=0 (int) but got {payload.get('keep_alive')!r}"
        )
        assert isinstance(payload.get("keep_alive"), int), (
            f"keep_alive must be int, got {type(payload.get('keep_alive'))}"
        )

    @pytest.mark.integration
    def test_load_model_returns_name(
        self, ollama_host, skip_if_no_ollama, first_generative_model
    ):
        """Scenario: Load Model loads model into Ollama memory."""
        (result,) = OllamaLoadModel().load_model(
            client=ollama_host, model=first_generative_model
        )
        assert result == first_generative_model

    def test_unload_returns_two_values(self):
        """OllamaUnloadModel returns (model_name, passthrough) tuple."""
        assert OllamaUnloadModel.RETURN_TYPES == ("STRING", "STRING")
        assert OllamaUnloadModel.RETURN_NAMES == ("model_name", "passthrough")

    def test_unload_passthrough_is_optional(self):
        """passthrough defaults to empty string when not wired."""
        inputs = OllamaUnloadModel.INPUT_TYPES()
        assert "passthrough" in inputs.get("optional", {}), (
            "passthrough must be optional — it creates the sequencing dependency "
            "but must not break standalone use"
        )

    @pytest.mark.integration
    def test_unload_model_returns_name_and_passthrough(
        self, ollama_host, skip_if_no_ollama, first_generative_model
    ):
        """Scenario: Unload evicts model; passthrough flows through unchanged."""
        model_name, passthrough = OllamaUnloadModel().unload_model(
            client=ollama_host,
            model=first_generative_model,
            passthrough="sentinel",
        )
        assert model_name == first_generative_model
        assert passthrough == "sentinel"


# ---------------------------------------------------------------------------
# US4 — Chat Completion  (us4_chat_completion.feature)
# ---------------------------------------------------------------------------

_CHAT_MODEL = "lukey03/qwen3.5-9b-abliterated-vision:latest"


class TestUS4ChatCompletion:
    def test_chat_completion_model_is_plain_string(self):
        """model input must be STRING (not COMBO) so it can receive wired values.

        COMBO inputs cannot accept wired connections. Using STRING lets users
        wire OllamaLoadModel.model_name → OllamaChatCompletion.model directly,
        removing the need for a separate model_name socket.
        """
        input_types = OllamaChatCompletion.INPUT_TYPES()
        model_input = input_types["required"]["model"]
        assert model_input[0] == "STRING", (
            f"OllamaChatCompletion model input must be STRING so it can be wired, "
            f"got {model_input[0]!r}"
        )

    def test_chat_has_no_model_name_input(self):
        """model_name optional input must be removed — model STRING accepts wired values."""
        inputs = OllamaChatCompletion.INPUT_TYPES()
        assert "model_name" not in inputs.get("optional", {}), (
            "model_name optional input is redundant now that model is a plain STRING "
            "that accepts wired connections"
        )

    def test_chat_model_receives_wired_string(self, monkeypatch):
        """Wiring OllamaLoadModel.model_name → OllamaChatCompletion.model works."""
        captured = {}

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            captured["model"] = payload.get("model")
            return {"message": {"content": "ok"}}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        _, _, used_model = OllamaChatCompletion().chat(
            client="http://localhost:11434",
            model="llama3:latest",
            prompt="hi",
        )["result"]
        assert used_model == "llama3:latest"
        assert captured.get("model") == "llama3:latest"

    def test_chat_completion_returns_model_name(self):
        """Third return value carries the effective model name for downstream unload."""
        assert OllamaChatCompletion.RETURN_TYPES == (
            "STRING",
            "OLLAMA_HISTORY",
            "STRING",
        )
        assert OllamaChatCompletion.RETURN_NAMES == (
            "response",
            "updated_history",
            "model_name",
        )

    def test_chat_is_output_node(self):
        """OllamaChatCompletion must have OUTPUT_NODE=True for inline display."""
        assert getattr(OllamaChatCompletion, "OUTPUT_NODE", False) is True

    def test_chat_returns_ui_result_dict(self, monkeypatch):
        """chat() must return {'ui': ..., 'result': ...} not a bare tuple."""

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            return {"message": {"content": "hello"}}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        ret = OllamaChatCompletion().chat(client="http://x", model="m", prompt="hi")
        assert isinstance(ret, dict), f"Expected dict, got {type(ret)}"
        assert "ui" in ret, "Missing 'ui' key"
        assert "result" in ret, "Missing 'result' key"

    def test_chat_ui_contains_response_text(self, monkeypatch):
        """Response text must appear in ui['text'] for the inline display."""

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            return {"message": {"content": "hello world"}}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        ret = OllamaChatCompletion().chat(client="http://x", model="m", prompt="hi")
        assert "hello world" in ret["ui"]["text"][0]

    def test_chat_result_is_3_tuple(self, monkeypatch):
        """result key must be the 3-tuple (response, history, model_name)."""

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            return {"message": {"content": "hello"}}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        ret = OllamaChatCompletion().chat(client="http://x", model="m", prompt="hi")
        assert isinstance(ret["result"], tuple)
        assert len(ret["result"]) == 3
        response, history, model_name = ret["result"]
        assert response == "hello"
        assert isinstance(history, list)
        assert model_name == "m"

    # ---- Issue 6: Chat timeout widget -----------------------------------------

    def test_chat_has_timeout_secs_input(self):
        """Issue 6: OllamaChatCompletion must expose a timeout_secs input widget.

        Currently INPUT_TYPES() does not include 'timeout_secs'.
        """
        input_types = OllamaChatCompletion.INPUT_TYPES()
        all_inputs = {
            **input_types.get("required", {}),
            **input_types.get("optional", {}),
        }
        assert "timeout_secs" in all_inputs, (
            "OllamaChatCompletion.INPUT_TYPES() must include 'timeout_secs' "
            "(in required or optional)"
        )

    def test_chat_timeout_forwarded_to_http(self, monkeypatch):
        """Issue 6: timeout_secs kwarg must be forwarded to _post_json's timeout param.

        Currently the chat() method does not accept timeout_secs, so this raises
        TypeError before reaching _post_json.
        """
        captured = {}

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            captured["timeout"] = timeout
            return {"message": {"content": "ok"}}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        OllamaChatCompletion().chat(
            client="http://x",
            model="m",
            prompt="p",
            timeout_secs=600,
        )

        assert captured.get("timeout") == 600.0, (
            f"Expected timeout forwarded as 600.0 but got {captured.get('timeout')!r}"
        )

    @pytest.mark.integration
    def test_single_turn_returns_non_empty_response(
        self, ollama_host, skip_if_no_ollama
    ):
        """Scenario: Single-turn completion returns non-empty response."""
        response, updated_history, model_name = OllamaChatCompletion().chat(
            client=ollama_host,
            model=_CHAT_MODEL,
            prompt="Say exactly the word: pong",
            history=[],
        )["result"]
        assert isinstance(response, str)
        assert len(response) > 0
        assert len(updated_history) == 2
        assert updated_history[0]["role"] == "user"
        assert updated_history[1]["role"] == "assistant"
        assert model_name == _CHAT_MODEL

    @pytest.mark.integration
    def test_multi_turn_receives_context(self, ollama_host, skip_if_no_ollama):
        """Scenario: Multi-turn completion receives full conversation context.

        Passes think=False to prevent Qwen3-family models from returning all
        output as thinking tokens with an empty content field.
        """
        no_think = {"think": False}
        _, history, _ = OllamaChatCompletion().chat(
            client=ollama_host,
            model=_CHAT_MODEL,
            prompt="My name is Alice. Remember it.",
            history=[],
            options=no_think,
        )["result"]
        response, updated, _ = OllamaChatCompletion().chat(
            client=ollama_host,
            model=_CHAT_MODEL,
            prompt="What is my name?",
            history=history,
            options=no_think,
        )["result"]
        assert "Alice" in response
        assert len(updated) == 4

    @pytest.mark.integration
    def test_history_accumulated_correctly(self, ollama_host, skip_if_no_ollama):
        """History list grows by 2 entries per turn."""
        _, h1, _ = OllamaChatCompletion().chat(
            client=ollama_host, model=_CHAT_MODEL, prompt="Turn 1", history=[]
        )["result"]
        assert len(h1) == 2
        _, h2, _ = OllamaChatCompletion().chat(
            client=ollama_host, model=_CHAT_MODEL, prompt="Turn 2", history=h1
        )["result"]
        assert len(h2) == 4


# ---------------------------------------------------------------------------
# US5 — Composable Options  (us5_composable_options.feature)
# ---------------------------------------------------------------------------


class TestUS5ComposableOptions:
    def test_temperature_sets_key(self):
        (opts,) = OllamaOptionTemperature().set_temperature(temperature=0.5)
        assert opts == {"temperature": 0.5}

    def test_temperature_merges_existing(self):
        (opts,) = OllamaOptionTemperature().set_temperature(
            temperature=0.0, options={"seed": 42}
        )
        assert opts == {"seed": 42, "temperature": 0.0}

    def test_seed_sets_key(self):
        (opts,) = OllamaOptionSeed().set_seed(seed=42)
        assert opts == {"seed": 42}

    def test_max_tokens_sets_num_predict(self):
        (opts,) = OllamaOptionMaxTokens().set_max_tokens(max_tokens=256)
        assert opts == {"num_predict": 256}

    def test_top_p_sets_key(self):
        (opts,) = OllamaOptionTopP().set_top_p(top_p=0.9)
        assert opts == {"top_p": 0.9}

    def test_top_k_sets_key(self):
        (opts,) = OllamaOptionTopK().set_top_k(top_k=40)
        assert opts == {"top_k": 40}

    def test_repeat_penalty_sets_key(self):
        (opts,) = OllamaOptionRepeatPenalty().set_repeat_penalty(repeat_penalty=1.1)
        assert opts == {"repeat_penalty": 1.1}

    def test_extra_body_merges_json(self):
        (opts,) = OllamaOptionExtraBody().set_extra_body(
            extra_body_json='{"stop": ["</s>"]}', options={"temperature": 0.0}
        )
        assert opts == {"temperature": 0.0, "stop": ["</s>"]}

    def test_extra_body_invalid_json_raises(self):
        with pytest.raises(ValueError, match="not valid JSON"):
            OllamaOptionExtraBody().set_extra_body(extra_body_json="not json")

    def test_chained_options_accumulate(self):
        """Scenario: Chained option nodes both reach the Ollama API."""
        (o1,) = OllamaOptionTemperature().set_temperature(temperature=0.0)
        (o2,) = OllamaOptionSeed().set_seed(seed=42, options=o1)
        assert o2 == {"temperature": 0.0, "seed": 42}

    def test_options_none_returns_single_key(self):
        """Scenario: Missing options input uses Ollama server defaults."""
        (opts,) = OllamaOptionTemperature().set_temperature(
            temperature=0.8, options=None
        )
        assert opts == {"temperature": 0.8}

    @pytest.mark.integration
    def test_temperature_zero_is_deterministic(self, ollama_host, skip_if_no_ollama):
        """Scenario: Temperature 0.0 produces deterministic output."""
        (opts,) = OllamaOptionTemperature().set_temperature(temperature=0.0)
        (opts2,) = OllamaOptionSeed().set_seed(seed=42, options=opts)
        kwargs = dict(
            client=ollama_host,
            model=_CHAT_MODEL,
            prompt="Say exactly the word: pong",
            history=[],
            options=opts2,
        )
        r1, _, _model = OllamaChatCompletion().chat(**kwargs)["result"]
        r2, _, _model = OllamaChatCompletion().chat(**kwargs)["result"]
        assert r1 == r2


# ---------------------------------------------------------------------------
# US6 — History Inspection  (us6_history_inspection.feature)
# ---------------------------------------------------------------------------


class TestUS6HistoryInspection:
    def test_debug_history_two_turns(self):
        """Scenario: Debug History shows both turns as a string."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        (debug_str,) = OllamaDebugHistory().debug(history=history)
        assert isinstance(debug_str, str)
        parsed = json.loads(debug_str)
        assert len(parsed) == 2
        assert parsed[0]["role"] == "user"
        assert parsed[1]["role"] == "assistant"

    def test_debug_history_empty(self):
        """Scenario: Empty history is handled gracefully (OllamaDebugHistory)."""
        (debug_str,) = OllamaDebugHistory().debug(history=[])
        assert debug_str in ("[]", json.dumps([], indent=2))

    def test_history_length_three(self):
        """Scenario: History Length counts turns correctly."""
        history = [
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "B"},
            {"role": "user", "content": "C"},
        ]
        (length,) = OllamaHistoryLength().length(history=history)
        assert length == 3

    def test_history_length_empty(self):
        """Scenario: Empty history is handled gracefully (OllamaHistoryLength)."""
        (length,) = OllamaHistoryLength().length(history=[])
        assert length == 0


# ---------------------------------------------------------------------------
# US7 — Auth headers
# ---------------------------------------------------------------------------


class TestUS7AuthHeaders:
    def test_client_without_headers_has_empty_dict(self):
        (client,) = OllamaClient().create_client("http://localhost:11434")
        assert client.headers == {}

    def test_client_carries_headers(self):
        (client,) = OllamaClient().create_client(
            "http://localhost:11434", headers={"Authorization": "Bearer abc"}
        )
        assert client.headers == {"Authorization": "Bearer abc"}
        assert client == "http://localhost:11434", (
            "OllamaClientType must still compare equal to the plain host string"
        )

    def test_basic_auth_sets_authorization_header(self):
        (headers,) = OllamaHeaderBasicAuth().set_basic_auth(
            username="alice", password="hunter2"
        )
        assert headers["Authorization"].startswith("Basic ")

    def test_basic_auth_encodes_username_password(self):
        import base64

        (headers,) = OllamaHeaderBasicAuth().set_basic_auth(
            username="alice", password="hunter2"
        )
        token = headers["Authorization"].removeprefix("Basic ")
        assert base64.b64decode(token).decode() == "alice:hunter2"

    def test_bearer_token_sets_authorization_header(self):
        (headers,) = OllamaHeaderBearerToken().set_bearer_token(token="sk-12345")
        assert headers == {"Authorization": "Bearer sk-12345"}

    def test_custom_header_sets_arbitrary_name(self):
        (headers,) = OllamaHeaderCustom().set_custom_header(
            name="X-Api-Key", value="abc123"
        )
        assert headers == {"X-Api-Key": "abc123"}

    def test_custom_header_empty_name_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            OllamaHeaderCustom().set_custom_header(name="", value="abc123")

    def test_headers_chain_and_merge(self):
        """Scenario: Bearer token + a custom header both reach the request."""
        (h1,) = OllamaHeaderBearerToken().set_bearer_token(token="sk-12345")
        (h2,) = OllamaHeaderCustom().set_custom_header(
            name="X-Api-Key", value="abc123", headers=h1
        )
        assert h2 == {"Authorization": "Bearer sk-12345", "X-Api-Key": "abc123"}

    def test_load_model_forwards_client_headers(self, monkeypatch):
        captured = {}

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            captured["headers"] = headers
            return {}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        (client,) = OllamaClient().create_client(
            "http://localhost:11434", headers={"Authorization": "Bearer sk-1"}
        )
        OllamaLoadModel().load_model(client=client, model="test-model")

        assert captured["headers"] == {"Authorization": "Bearer sk-1"}

    def test_unload_model_forwards_client_headers(self, monkeypatch):
        captured = {}

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            captured["headers"] = headers
            return {}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        (client,) = OllamaClient().create_client(
            "http://localhost:11434", headers={"Authorization": "Bearer sk-1"}
        )
        OllamaUnloadModel().unload_model(client=client, model="test-model")

        assert captured["headers"] == {"Authorization": "Bearer sk-1"}

    def test_chat_forwards_client_headers(self, monkeypatch):
        captured = {}

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            captured["headers"] = headers
            return {"message": {"content": "ok"}}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        (client,) = OllamaClient().create_client(
            "http://localhost:11434", headers={"Authorization": "Bearer sk-1"}
        )
        OllamaChatCompletion().chat(client=client, model="m", prompt="hi")

        assert captured["headers"] == {"Authorization": "Bearer sk-1"}

    def test_plain_string_client_has_no_headers(self, monkeypatch):
        """Backward compat: a bare string client (no OllamaClient node) sends no headers."""
        captured = {}

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            captured["headers"] = headers
            return {"message": {"content": "ok"}}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        OllamaChatCompletion().chat(
            client="http://localhost:11434", model="m", prompt="hi"
        )

        assert captured["headers"] is None


# ---------------------------------------------------------------------------
# Response cache — model discovery + chat completion
# ---------------------------------------------------------------------------


class TestResponseCache:
    def test_fetch_models_second_call_is_cached(self, monkeypatch):
        calls = {"n": 0}

        class FakeResponse:
            status = 200

            async def json(self):
                calls["n"] += 1
                return {"models": [{"name": "llama3:latest"}]}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        class FakeSession:
            def get(self, url, *, headers=None, timeout=None):
                return FakeResponse()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        import aiohttp

        monkeypatch.setattr(aiohttp, "ClientSession", lambda: FakeSession())

        models1 = _run_async(_fetch_models("http://localhost:11434"))
        models2 = _run_async(_fetch_models("http://localhost:11434"))

        assert models1 == models2 == ["llama3:latest"]
        assert calls["n"] == 1, "second call with identical inputs must hit the cache"

    def test_fetch_models_different_host_not_cached(self, monkeypatch):
        calls = {"n": 0}

        class FakeResponse:
            status = 200

            async def json(self):
                calls["n"] += 1
                return {"models": [{"name": "llama3:latest"}]}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        class FakeSession:
            def get(self, url, *, headers=None, timeout=None):
                return FakeResponse()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        import aiohttp

        monkeypatch.setattr(aiohttp, "ClientSession", lambda: FakeSession())

        _run_async(_fetch_models("http://host-a:11434"))
        _run_async(_fetch_models("http://host-b:11434"))

        assert calls["n"] == 2, "different hosts must not share a cache entry"

    def test_fetch_models_ttl_expiry_refetches(self, monkeypatch):
        """A newly-installed model must surface once the TTL lapses."""
        calls = {"n": 0}

        class FakeResponse:
            status = 200

            async def json(self):
                calls["n"] += 1
                return {"models": [{"name": "llama3:latest"}]}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        class FakeSession:
            def get(self, url, *, headers=None, timeout=None):
                return FakeResponse()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        import aiohttp

        monkeypatch.setattr(aiohttp, "ClientSession", lambda: FakeSession())

        _run_async(_fetch_models("http://localhost:11434"))
        assert calls["n"] == 1

        # Simulate TTL lapsing by clearing the cache directly rather than
        # sleeping in a unit test.
        _MODEL_LIST_CACHE.clear()

        _run_async(_fetch_models("http://localhost:11434"))
        assert calls["n"] == 2

    def test_chat_second_identical_call_is_cached(self, monkeypatch):
        calls = {"n": 0}

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            calls["n"] += 1
            return {"message": {"content": f"response #{calls['n']}"}}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        r1, _, _ = OllamaChatCompletion().chat(
            client="http://x", model="m", prompt="hi"
        )["result"]
        r2, _, _ = OllamaChatCompletion().chat(
            client="http://x", model="m", prompt="hi"
        )["result"]

        assert r1 == r2 == "response #1"
        assert calls["n"] == 1, "identical chat inputs must reuse the cached response"

    def test_chat_different_prompt_not_cached(self, monkeypatch):
        calls = {"n": 0}

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            calls["n"] += 1
            return {"message": {"content": f"response #{calls['n']}"}}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        OllamaChatCompletion().chat(client="http://x", model="m", prompt="hi")
        OllamaChatCompletion().chat(client="http://x", model="m", prompt="bye")

        assert calls["n"] == 2, "different prompts must not share a cache entry"

    def test_chat_different_options_not_cached(self, monkeypatch):
        calls = {"n": 0}

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            calls["n"] += 1
            return {"message": {"content": f"response #{calls['n']}"}}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        OllamaChatCompletion().chat(
            client="http://x", model="m", prompt="hi", options={"temperature": 0.0}
        )
        OllamaChatCompletion().chat(
            client="http://x", model="m", prompt="hi", options={"temperature": 0.9}
        )

        assert calls["n"] == 2, "different options must not share a cache entry"

    def test_chat_grown_history_not_cached(self, monkeypatch):
        """A follow-up turn (different message history) must not reuse turn 1's cache entry."""
        calls = {"n": 0}

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            calls["n"] += 1
            return {"message": {"content": f"response #{calls['n']}"}}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        _, h1, _ = OllamaChatCompletion().chat(
            client="http://x", model="m", prompt="turn 1", history=[]
        )["result"]
        OllamaChatCompletion().chat(
            client="http://x", model="m", prompt="turn 2", history=h1
        )

        assert calls["n"] == 2

    def test_chat_different_client_headers_not_cached(self, monkeypatch):
        calls = {"n": 0}

        async def fake_post(url, payload, *, timeout=120.0, headers=None):
            calls["n"] += 1
            return {"message": {"content": f"response #{calls['n']}"}}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        (client_a,) = OllamaClient().create_client(
            "http://x", headers={"Authorization": "Bearer a"}
        )
        (client_b,) = OllamaClient().create_client(
            "http://x", headers={"Authorization": "Bearer b"}
        )

        OllamaChatCompletion().chat(client=client_a, model="m", prompt="hi")
        OllamaChatCompletion().chat(client=client_b, model="m", prompt="hi")

        assert calls["n"] == 2, (
            "requests to the same host with different auth headers must not share "
            "a cache entry"
        )


# ---------------------------------------------------------------------------
# Node contract sanity checks (ComfyUI registration requirements)
# ---------------------------------------------------------------------------


class TestNodeContracts:
    """All 17 nodes must satisfy ComfyUI's node registration contract."""

    NODE_CLASSES = [
        OllamaClient,
        OllamaModelSelector,
        OllamaLoadModel,
        OllamaUnloadModel,
        OllamaChatCompletion,
        OllamaOptionTemperature,
        OllamaOptionSeed,
        OllamaOptionMaxTokens,
        OllamaOptionTopP,
        OllamaOptionTopK,
        OllamaOptionRepeatPenalty,
        OllamaOptionExtraBody,
        OllamaDebugHistory,
        OllamaHistoryLength,
        OllamaHeaderBasicAuth,
        OllamaHeaderBearerToken,
        OllamaHeaderCustom,
    ]

    @pytest.mark.parametrize("node_cls", NODE_CLASSES, ids=lambda c: c.__name__)
    def test_has_required_attributes(self, node_cls):
        assert hasattr(node_cls, "INPUT_TYPES"), (
            f"{node_cls.__name__} missing INPUT_TYPES"
        )
        assert callable(node_cls.INPUT_TYPES)
        assert hasattr(node_cls, "RETURN_TYPES"), (
            f"{node_cls.__name__} missing RETURN_TYPES"
        )
        assert hasattr(node_cls, "FUNCTION"), f"{node_cls.__name__} missing FUNCTION"
        assert hasattr(node_cls, "CATEGORY"), f"{node_cls.__name__} missing CATEGORY"
        assert hasattr(node_cls, node_cls.FUNCTION), (
            f"{node_cls.__name__}.FUNCTION='{node_cls.FUNCTION}' but method doesn't exist"
        )

    @pytest.mark.parametrize("node_cls", NODE_CLASSES, ids=lambda c: c.__name__)
    def test_input_types_structure(self, node_cls):
        types = node_cls.INPUT_TYPES()
        assert isinstance(types, dict)
        assert "required" in types or "optional" in types
