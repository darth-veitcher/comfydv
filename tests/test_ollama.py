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

import json

import pytest

from comfydv.ollama import (
    OllamaChatCompletion,
    OllamaClient,
    OllamaClientType,
    OllamaDebugHistory,
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
    _fetch_models,
    _run_async,
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

    @pytest.mark.integration
    def test_load_model_returns_name(self, ollama_host, skip_if_no_ollama):
        """Scenario: Load Model loads model into Ollama memory."""
        (result,) = OllamaLoadModel().load_model(
            client=ollama_host, model="embeddinggemma:latest"
        )
        assert result == "embeddinggemma:latest"

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
        self, ollama_host, skip_if_no_ollama
    ):
        """Scenario: Unload evicts model; passthrough flows through unchanged."""
        model_name, passthrough = OllamaUnloadModel().unload_model(
            client=ollama_host,
            model="embeddinggemma:latest",
            passthrough="sentinel",
        )
        assert model_name == "embeddinggemma:latest"
        assert passthrough == "sentinel"


# ---------------------------------------------------------------------------
# US4 — Chat Completion  (us4_chat_completion.feature)
# ---------------------------------------------------------------------------

_CHAT_MODEL = "lukey03/qwen3.5-9b-abliterated-vision:latest"


class TestUS4ChatCompletion:
    def test_chat_completion_input_types_uses_combo(self):
        """Scenario: Chat Completion shows live dropdown (fixes Issue #1)."""
        input_types = OllamaChatCompletion.INPUT_TYPES()
        model_input = input_types["required"]["model"]
        assert isinstance(model_input[0], list), (
            "OllamaChatCompletion model input must be a COMBO (list) — Issue #1 fix"
        )

    def test_chat_completion_accepts_wired_model_name(self):
        """model_name optional input lets OllamaLoadModel.model_name wire in for ordering."""
        inputs = OllamaChatCompletion.INPUT_TYPES()
        assert "model_name" in inputs.get("optional", {}), (
            "model_name must be optional so LoadModel can wire its output here "
            "to guarantee Load → Chat execution order"
        )

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

    def test_wired_model_name_overrides_combo(self, monkeypatch):
        """model_name kwarg takes precedence over the COMBO widget value."""
        captured = {}

        async def fake_post(url, payload):
            captured["model"] = payload.get("model")
            return {"message": {"content": "ok"}}

        import comfydv.ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "_post_json", fake_post)

        response, _, effective = OllamaChatCompletion().chat(
            client="http://localhost:11434",
            model="dropdown-value",
            prompt="hi",
            model_name="wired-value",
        )
        assert effective == "wired-value"
        assert captured.get("model") == "wired-value"

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
        )
        assert isinstance(response, str)
        assert len(response) > 0
        assert len(updated_history) == 2
        assert updated_history[0]["role"] == "user"
        assert updated_history[1]["role"] == "assistant"
        assert model_name == _CHAT_MODEL

    @pytest.mark.integration
    def test_multi_turn_receives_context(self, ollama_host, skip_if_no_ollama):
        """Scenario: Multi-turn completion receives full conversation context."""
        _, history, _ = OllamaChatCompletion().chat(
            client=ollama_host,
            model=_CHAT_MODEL,
            prompt="My name is Alice. Remember it.",
            history=[],
        )
        response, updated, _ = OllamaChatCompletion().chat(
            client=ollama_host,
            model=_CHAT_MODEL,
            prompt="What is my name?",
            history=history,
        )
        assert "Alice" in response
        assert len(updated) == 4

    @pytest.mark.integration
    def test_history_accumulated_correctly(self, ollama_host, skip_if_no_ollama):
        """History list grows by 2 entries per turn."""
        _, h1, _ = OllamaChatCompletion().chat(
            client=ollama_host, model=_CHAT_MODEL, prompt="Turn 1", history=[]
        )
        assert len(h1) == 2
        _, h2, _ = OllamaChatCompletion().chat(
            client=ollama_host, model=_CHAT_MODEL, prompt="Turn 2", history=h1
        )
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
        r1, _ = OllamaChatCompletion().chat(**kwargs)
        r2, _ = OllamaChatCompletion().chat(**kwargs)
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
# Node contract sanity checks (ComfyUI registration requirements)
# ---------------------------------------------------------------------------


class TestNodeContracts:
    """All 14 nodes must satisfy ComfyUI's node registration contract."""

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
