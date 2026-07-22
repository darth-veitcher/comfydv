"""
Tests for comfydv.ollama — generic LLM nodes (ADR-007) backed by Ollama.

Node-contract and delegation tests only: does each node expose the right
ComfyUI shape, and does it call the right LLMProvider method with the right
arguments? A `_FakeProvider` test double stands in for `client` throughout —
this file never mocks aiohttp/_post_json directly. OllamaProvider's actual
Ollama-wire-protocol behavior (keep_alive payloads, /api/tags parsing,
header/timeout forwarding, caching) is tested in test_ollama_provider.py;
the shared pydantic-ai structured-output mechanism is tested in
test_llm_chat_structured.py. See
specs/007-llm-provider-abstraction/atomic-cutover-plan.md D4/D5 for why
coverage is split this way.

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
  ../specs/007-llm-provider-abstraction/features/us1_connect_and_chat.feature
  ../specs/007-llm-provider-abstraction/features/us2_structured_output.feature
  ../specs/007-llm-provider-abstraction/features/us3_model_lifecycle.feature
  ../specs/007-llm-provider-abstraction/features/us4_migration.feature
"""

import json

import pytest

from comfydv._llm.ollama_provider import OllamaProvider
from comfydv.ollama import (
    ChatCompletion,
    LLMLoadModel,
    LLMModelSelector,
    LLMUnloadModel,
    MIGRATION_MAP,
    OllamaClient,
    OllamaDebugHistory,
    OllamaHeaderBasicAuth,
    OllamaHeaderBearerToken,
    OllamaHeaderCustom,
    OllamaHistoryLength,
    OllamaOptionExtraBody,
    OllamaOptionMaxTokens,
    OllamaOptionRepeatPenalty,
    OllamaOptionSeed,
    OllamaOptionTemperature,
    OllamaOptionTopK,
    OllamaOptionTopP,
)


# ---------------------------------------------------------------------------
# Test double — stands in for `client` (an LLMProvider) throughout this file
# ---------------------------------------------------------------------------


class _FakeProvider:
    """Records calls, returns scripted values. See module docstring."""

    def __init__(
        self,
        *,
        models=None,
        chat_response="ok",
        structured_field_values=None,
        raise_on_chat_structured=None,
    ):
        self.models = models or []
        self.chat_response = chat_response
        self.structured_field_values = structured_field_values or {}
        self.raise_on_chat_structured = raise_on_chat_structured
        self.calls: list[tuple] = []

    async def list_models(self):
        self.calls.append(("list_models",))
        return self.models

    async def load_model(self, model):
        self.calls.append(("load_model", model))

    async def unload_model(self, model):
        self.calls.append(("unload_model", model))

    async def chat(
        self, model, messages, options=None, timeout_secs=300.0, max_retries=2
    ):
        self.calls.append(("chat", model, messages, options, timeout_secs, max_retries))
        return self.chat_response

    async def chat_structured(
        self, model, messages, schema, options=None, timeout_secs=300.0, max_retries=2
    ):
        self.calls.append(
            (
                "chat_structured",
                model,
                messages,
                schema,
                options,
                timeout_secs,
                max_retries,
            )
        )
        if self.raise_on_chat_structured is not None:
            raise self.raise_on_chat_structured
        return schema(**self.structured_field_values)


# ---------------------------------------------------------------------------
# US1 — Ollama Connection  (us1_ollama_connection.feature)
# ---------------------------------------------------------------------------


class TestUS1OllamaConnection:
    def test_client_outputs_ollama_provider(self):
        """Scenario: Default host connects to local Ollama."""
        (client,) = OllamaClient().create_client("http://localhost:11434")
        assert isinstance(client, OllamaProvider)
        assert client.host == "http://localhost:11434"

    def test_client_custom_host_is_preserved(self):
        """Scenario: Host change causes widgets to refresh."""
        (client,) = OllamaClient().create_client("http://myserver:11434")
        assert client.host == "http://myserver:11434"

    @pytest.mark.integration
    def test_unreachable_host_raises_named_error(self, skip_if_no_ollama):
        """Scenario: Unreachable host surfaces a named error."""
        (client,) = OllamaClient().create_client("http://localhost:19999")
        with pytest.raises(RuntimeError, match="Cannot reach Ollama"):
            LLMLoadModel().load_model(client=client, model="embeddinggemma:latest")


# ---------------------------------------------------------------------------
# US2 — Model Selection  (us2_model_selection.feature)
# ---------------------------------------------------------------------------


class TestUS2ModelSelection:
    def test_model_selector_output_is_exact_name(self):
        """Scenario: Selected model name is the node output."""
        fake = _FakeProvider()
        (result,) = LLMModelSelector().select_model(client=fake, model="llama3:latest")
        assert result == "llama3:latest"
        assert fake.calls == [], "select_model is pure passthrough — no provider call"

    def test_model_selector_input_types_uses_combo(self):
        """Scenario: LLMModelSelector shows a dropdown (not a text box)."""
        input_types = LLMModelSelector.INPUT_TYPES()
        model_input = input_types["required"]["model"]
        assert isinstance(model_input[0], list), (
            "model input must be a COMBO (list), not STRING"
        )


# ---------------------------------------------------------------------------
# US3 — Model Lifecycle  (us3_model_lifecycle.feature)
# ---------------------------------------------------------------------------


class TestUS3ModelLifecycle:
    def test_load_model_input_types_uses_combo(self):
        input_types = LLMLoadModel.INPUT_TYPES()
        model_input = input_types["required"]["model"]
        assert isinstance(model_input[0], list)

    def test_empty_model_raises_before_provider_call(self):
        fake = _FakeProvider()
        with pytest.raises(ValueError, match="cannot be empty"):
            LLMLoadModel().load_model(client=fake, model="")
        assert fake.calls == []

    def test_empty_model_whitespace_raises(self):
        fake = _FakeProvider()
        with pytest.raises(ValueError, match="cannot be empty"):
            LLMLoadModel().load_model(client=fake, model="   ")
        assert fake.calls == []

    def test_unload_empty_model_raises(self):
        fake = _FakeProvider()
        with pytest.raises(ValueError, match="cannot be empty"):
            LLMUnloadModel().unload_model(client=fake, model="")
        assert fake.calls == []

    def test_load_model_delegates_to_provider(self):
        fake = _FakeProvider()
        (result,) = LLMLoadModel().load_model(client=fake, model="llama3:latest")
        assert result == "llama3:latest"
        assert fake.calls == [("load_model", "llama3:latest")]

    def test_unload_model_delegates_to_provider(self):
        fake = _FakeProvider()
        result = LLMUnloadModel().unload_model(
            client=fake, model="llama3:latest", passthrough="sentinel"
        )
        assert result == ("llama3:latest", "sentinel")
        assert fake.calls == [("unload_model", "llama3:latest")]

    def test_unload_returns_two_values(self):
        assert LLMUnloadModel.RETURN_TYPES == ("STRING", "STRING")
        assert LLMUnloadModel.RETURN_NAMES == ("model_name", "passthrough")

    def test_unload_passthrough_is_optional(self):
        inputs = LLMUnloadModel.INPUT_TYPES()
        assert "passthrough" in inputs.get("optional", {}), (
            "passthrough must be optional — it creates the sequencing dependency "
            "but must not break standalone use"
        )

    @pytest.mark.integration
    def test_load_model_returns_name(
        self, ollama_host, skip_if_no_ollama, first_generative_model
    ):
        """Scenario: Load Model loads model into Ollama memory."""
        (client,) = OllamaClient().create_client(ollama_host)
        (result,) = LLMLoadModel().load_model(
            client=client, model=first_generative_model
        )
        assert result == first_generative_model

    @pytest.mark.integration
    def test_unload_model_returns_name_and_passthrough(
        self, ollama_host, skip_if_no_ollama, first_generative_model
    ):
        """Scenario: Unload evicts model; passthrough flows through unchanged."""
        (client,) = OllamaClient().create_client(ollama_host)
        model_name, passthrough = LLMUnloadModel().unload_model(
            client=client,
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
        wire LLMLoadModel.model_name → ChatCompletion.model directly, removing
        the need for a separate model_name socket.
        """
        input_types = ChatCompletion.INPUT_TYPES()
        model_input = input_types["required"]["model"]
        assert model_input[0] == "STRING", (
            f"ChatCompletion model input must be STRING so it can be wired, "
            f"got {model_input[0]!r}"
        )

    def test_chat_has_no_model_name_input(self):
        inputs = ChatCompletion.INPUT_TYPES()
        assert "model_name" not in inputs.get("optional", {})

    def test_chat_model_receives_wired_string(self):
        """Wiring LLMLoadModel.model_name → ChatCompletion.model works."""
        fake = _FakeProvider(chat_response="ok")
        _, _, used_model = ChatCompletion().chat(
            client=fake, model="llama3:latest", prompt="hi"
        )["result"]
        assert used_model == "llama3:latest"
        assert fake.calls[0][0] == "chat"
        assert fake.calls[0][1] == "llama3:latest"

    def test_chat_completion_returns_model_name(self):
        assert ChatCompletion.RETURN_TYPES == ("STRING", "OLLAMA_HISTORY", "STRING")
        assert ChatCompletion.RETURN_NAMES == (
            "response",
            "updated_history",
            "model_name",
        )

    def test_chat_is_output_node(self):
        assert getattr(ChatCompletion, "OUTPUT_NODE", False) is True

    def test_chat_returns_ui_result_dict(self):
        fake = _FakeProvider(chat_response="hello")
        ret = ChatCompletion().chat(client=fake, model="m", prompt="hi")
        assert isinstance(ret, dict)
        assert "ui" in ret
        assert "result" in ret

    def test_chat_ui_contains_response_text(self):
        fake = _FakeProvider(chat_response="hello world")
        ret = ChatCompletion().chat(client=fake, model="m", prompt="hi")
        assert "hello world" in ret["ui"]["text"][0]

    def test_chat_result_is_3_tuple(self):
        fake = _FakeProvider(chat_response="hello")
        ret = ChatCompletion().chat(client=fake, model="m", prompt="hi")
        assert isinstance(ret["result"], tuple)
        assert len(ret["result"]) == 3
        response, history, model_name = ret["result"]
        assert response == "hello"
        assert isinstance(history, list)
        assert model_name == "m"

    def test_chat_has_timeout_secs_input(self):
        input_types = ChatCompletion.INPUT_TYPES()
        all_inputs = {
            **input_types.get("required", {}),
            **input_types.get("optional", {}),
        }
        assert "timeout_secs" in all_inputs

    def test_chat_timeout_forwarded_to_provider(self):
        fake = _FakeProvider(chat_response="ok")
        ChatCompletion().chat(client=fake, model="m", prompt="p", timeout_secs=600)
        assert fake.calls[0][4] == 600.0

    def test_chat_empty_model_raises_before_provider_call(self):
        fake = _FakeProvider()
        with pytest.raises(ValueError, match="cannot be empty"):
            ChatCompletion().chat(client=fake, model="", prompt="hi")
        assert fake.calls == []

    @pytest.mark.integration
    def test_single_turn_returns_non_empty_response(
        self, ollama_host, skip_if_no_ollama
    ):
        """Scenario: Single-turn completion returns non-empty response."""
        (client,) = OllamaClient().create_client(ollama_host)
        response, updated_history, model_name = ChatCompletion().chat(
            client=client,
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
        (client,) = OllamaClient().create_client(ollama_host)
        no_think = {"think": False}
        _, history, _ = ChatCompletion().chat(
            client=client,
            model=_CHAT_MODEL,
            prompt="My name is Alice. Remember it.",
            history=[],
            options=no_think,
        )["result"]
        response, updated, _ = ChatCompletion().chat(
            client=client,
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
        (client,) = OllamaClient().create_client(ollama_host)
        _, h1, _ = ChatCompletion().chat(
            client=client, model=_CHAT_MODEL, prompt="Turn 1", history=[]
        )["result"]
        assert len(h1) == 2
        _, h2, _ = ChatCompletion().chat(
            client=client, model=_CHAT_MODEL, prompt="Turn 2", history=h1
        )["result"]
        assert len(h2) == 4

    @pytest.mark.integration
    def test_structured_output_retries_then_raises_against_live_server(
        self, ollama_host, skip_if_no_ollama
    ):
        """Scenario: structured_output's retry-then-raise fallback against a
        real server, using an unreliable model that empirically cannot be
        made to call the forced tool consistently.

        This intentionally does NOT assert a happy-path clean result — see
        the original ADR-006 rationale. What IS worth proving against a live
        server: the shared pydantic-ai mechanism (comfydv._llm.chat) makes
        genuine repeated network calls and produces a well-formed,
        diagnostic error rather than hanging, crashing uninformatively, or
        silently returning bad data. The happy path is covered by
        tests/test_llm_chat_structured.py's mocked suite.
        """
        (client,) = OllamaClient().create_client(ollama_host)
        with pytest.raises(RuntimeError) as exc_info:
            ChatCompletion().chat(
                client=client,
                model=_CHAT_MODEL,
                prompt="Say exactly: pong",
                options={"think": False},
                structured_output=True,
                output_schema=(
                    '{"type":"object","properties":{"output":{"type":"string"}},'
                    '"required":["output"]}'
                ),
                max_retries=1,
                unique_id="smoke-test",
            )
        assert _CHAT_MODEL in str(exc_info.value)


# ---------------------------------------------------------------------------
# US8 — Structured output. Schema-parsing helpers stay in ollama.py (pure,
# no network); the tool-calling/retry/validation mechanism moved to
# comfydv._llm.chat (pydantic-ai) as of ADR-007, superseding ADR-006's
# hand-rolled approach — see tests/test_llm_chat_structured.py for that
# mechanism's own coverage. Tests here only prove ChatCompletion wires
# structured_output through to client.chat_structured() correctly and
# extracts the resulting fields into the right ComfyUI output sockets.
# ---------------------------------------------------------------------------

_SINGLE_FIELD_SCHEMA = (
    '{"type": "object", "properties": {"output": {"type": "string"}}, '
    '"required": ["output"]}'
)
_MULTI_FIELD_SCHEMA = (
    '{"type": "object", "properties": {'
    '"summary": {"type": "string"}, '
    '"score": {"type": "integer"}, '
    '"is_positive": {"type": "boolean"}}, '
    '"required": ["summary", "score", "is_positive"]}'
)


class TestStructuredOutput:
    def test_structured_output_defaults_to_false(self):
        input_types = ChatCompletion.INPUT_TYPES()
        assert input_types["optional"]["structured_output"] == (
            "BOOLEAN",
            {"default": False},
        )

    def test_dispatches_to_chat_when_not_structured(self):
        fake = _FakeProvider(chat_response="hello")
        ChatCompletion().chat(
            client=fake, model="m", prompt="hi", structured_output=False
        )
        assert [c[0] for c in fake.calls] == ["chat"]

    def test_dispatches_to_chat_structured_when_structured(self):
        fake = _FakeProvider(structured_field_values={"output": "hi there"})
        ChatCompletion().chat(
            client=fake,
            model="m",
            prompt="hi",
            structured_output=True,
            output_schema=_SINGLE_FIELD_SCHEMA,
            unique_id="n1",
        )
        assert [c[0] for c in fake.calls] == ["chat_structured"]

    def test_default_schema_produces_single_output_field(self):
        fake = _FakeProvider(structured_field_values={"output": "clean text"})
        ret = ChatCompletion().chat(
            client=fake,
            model="m",
            prompt="hi",
            structured_output=True,
            unique_id="n2",
        )
        assert ChatCompletion.RETURN_NAMES == (
            "response",
            "updated_history",
            "model_name",
            "output",
        )
        assert len(ret["result"]) == 4
        assert ret["result"][3] == "clean text"
        assert json.loads(ret["result"][0]) == {"output": "clean text"}

    def test_multi_field_schema_sets_return_types_and_values(self):
        fake = _FakeProvider(
            structured_field_values={
                "summary": "great",
                "score": 9,
                "is_positive": True,
            }
        )
        ret = ChatCompletion().chat(
            client=fake,
            model="m",
            prompt="hi",
            structured_output=True,
            output_schema=_MULTI_FIELD_SCHEMA,
            unique_id="n3",
        )
        assert ChatCompletion.RETURN_TYPES == (
            "STRING",
            "OLLAMA_HISTORY",
            "STRING",
            "STRING",
            "INT",
            "BOOLEAN",
        )
        assert ChatCompletion.RETURN_NAMES == (
            "response",
            "updated_history",
            "model_name",
            "summary",
            "score",
            "is_positive",
        )
        _, _, _, summary, score, is_positive = ret["result"]
        assert summary == "great"
        assert score == 9
        assert isinstance(score, int)
        assert is_positive is True

    def test_array_object_property_json_dumped_into_string_slot(self):
        schema = (
            '{"type": "object", "properties": {'
            '"tags": {"type": "array"}}, "required": ["tags"]}'
        )
        fake = _FakeProvider(structured_field_values={"tags": ["a", "b", "c"]})
        ret = ChatCompletion().chat(
            client=fake,
            model="m",
            prompt="hi",
            structured_output=True,
            output_schema=schema,
            unique_id="n4",
        )
        assert ret["result"][3] == json.dumps(["a", "b", "c"])

    def test_return_types_reset_when_toggled_off(self):
        fake = _FakeProvider(structured_field_values={"output": "x"})
        ChatCompletion().chat(
            client=fake,
            model="m",
            prompt="hi",
            structured_output=True,
            unique_id="n5",
        )
        assert len(ChatCompletion.RETURN_TYPES) == 4

        fake2 = _FakeProvider(chat_response="x")
        ChatCompletion().chat(
            client=fake2,
            model="m",
            prompt="hi",
            structured_output=False,
            unique_id="n5",
        )
        assert ChatCompletion.RETURN_TYPES == ChatCompletion._BASE_RETURN_TYPES
        assert ChatCompletion.RETURN_NAMES == ChatCompletion._BASE_RETURN_NAMES

    def test_invalid_output_schema_json_raises_before_provider_call(self):
        fake = _FakeProvider()
        with pytest.raises(ValueError, match="not valid JSON"):
            ChatCompletion().chat(
                client=fake,
                model="m",
                prompt="hi",
                structured_output=True,
                output_schema="not json",
            )
        assert fake.calls == [], "invalid schema must fail before touching the provider"

    def test_non_object_root_schema_raises(self):
        fake = _FakeProvider()
        with pytest.raises(ValueError, match='"type": "object"'):
            ChatCompletion().chat(
                client=fake,
                model="m",
                prompt="hi",
                structured_output=True,
                output_schema='{"type": "string"}',
            )

    def test_empty_properties_raises(self):
        fake = _FakeProvider()
        with pytest.raises(ValueError, match="non-empty object"):
            ChatCompletion().chat(
                client=fake,
                model="m",
                prompt="hi",
                structured_output=True,
                output_schema='{"type": "object", "properties": {}}',
            )

    def test_max_retries_forwarded_to_provider(self):
        """Retry/exhaustion behavior itself is the shared pydantic-ai
        mechanism's responsibility — see test_llm_chat_structured.py. Here
        we only confirm ChatCompletion forwards max_retries unchanged."""
        fake = _FakeProvider(structured_field_values={"output": "ok"})
        ChatCompletion().chat(
            client=fake,
            model="m",
            prompt="hi",
            structured_output=True,
            max_retries=4,
        )
        assert fake.calls[0][6] == 4

    def test_provider_error_propagates(self):
        """A provider that exhausts retries raises RuntimeError — ChatCompletion
        must not swallow or reshape it (the error contract lives in
        comfydv._llm.chat now, not here)."""
        fake = _FakeProvider(
            raise_on_chat_structured=RuntimeError(
                "chat_structured: response failed validation ... 3 attempt(s) ..."
            )
        )
        with pytest.raises(RuntimeError, match="failed validation"):
            ChatCompletion().chat(
                client=fake, model="m", prompt="hi", structured_output=True
            )


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
        (client,) = OllamaClient().create_client(ollama_host)
        (opts,) = OllamaOptionTemperature().set_temperature(temperature=0.0)
        (opts2,) = OllamaOptionSeed().set_seed(seed=42, options=opts)
        kwargs = dict(
            client=client,
            model=_CHAT_MODEL,
            prompt="Say exactly the word: pong",
            history=[],
            options=opts2,
        )
        r1, _, _model = ChatCompletion().chat(**kwargs)["result"]
        r2, _, _model = ChatCompletion().chat(**kwargs)["result"]
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
        assert client.headers is None

    def test_client_carries_headers(self):
        (client,) = OllamaClient().create_client(
            "http://localhost:11434", headers={"Authorization": "Bearer abc"}
        )
        assert client.headers == {"Authorization": "Bearer abc"}
        assert client.host == "http://localhost:11434"

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

    # Header forwarding to the actual HTTP request is OllamaProvider's job now
    # (test_ollama_provider.py's test_load_model_forwards_headers etc.) — the
    # end-to-end path is fully composed from: OllamaClient building an
    # OllamaProvider with the right .headers (test_client_carries_headers
    # above), LLMLoadModel/LLMUnloadModel/ChatCompletion delegating to
    # whatever client they're given (TestUS3ModelLifecycle/TestUS4ChatCompletion
    # delegation tests), and OllamaProvider forwarding self.headers to
    # _post_json (test_ollama_provider.py). No bare-string `client` support —
    # that was an undocumented side effect of OllamaClientType being a str
    # subclass, removed per ADR-007 (atomic-cutover-plan.md D3), not migrated.


# ---------------------------------------------------------------------------
# Live structured-output socket preview route
# (mirrors FormatString's /update_format_string_node — see US8 above)
# ---------------------------------------------------------------------------


class _FakeRequest:
    def __init__(self, body: dict):
        self._body = body

    async def json(self):
        return self._body


class _FakeRelUrl:
    def __init__(self, query: dict):
        self.query = query


class _FakeGetRequest:
    def __init__(self, query: dict):
        self.rel_url = _FakeRelUrl(query)


class TestModelsRoute:
    """GET /dv/ollama/models — the JS refresh-button/auto-populate endpoint.

    Previously untested (no test survived the atomic cutover rewrite), which
    is exactly how a real bug shipped undetected: the `backend` dispatch
    added here didn't exist until a live js/ollama.js bug was found (it
    matched on pre-rename node names and always spoke Ollama's wire
    protocol regardless of which client was actually connected)."""

    def _call(self, query: dict):
        import comfydv.ollama as ollama_mod
        from comfydv._llm.ollama_provider import _run_async

        resp = _run_async(ollama_mod._models_endpoint(_FakeGetRequest(query)))
        return json.loads(resp.text), resp.status

    def test_default_backend_dispatches_to_ollama(self, monkeypatch):
        async def fake_fetch(host, headers=None):
            assert host == "http://localhost:11434"
            return ["a", "b"]

        monkeypatch.setattr("comfydv.ollama._fetch_models", fake_fetch)
        data, status = self._call({"host": "http://localhost:11434"})

        assert status == 200
        assert data == {"models": ["a", "b"]}

    def test_explicit_ollama_backend_dispatches_to_ollama(self, monkeypatch):
        async def fake_fetch(host, headers=None):
            return ["m"]

        monkeypatch.setattr("comfydv.ollama._fetch_models", fake_fetch)
        data, status = self._call(
            {"host": "http://localhost:11434", "backend": "ollama"}
        )

        assert status == 200
        assert data == {"models": ["m"]}

    def test_llamacpp_backend_dispatches_to_llamacpp_fetch(self, monkeypatch):
        """The bug this regression-tests: before the fix, this endpoint
        always called Ollama's _fetch_models regardless of `backend`, so a
        llama.cpp host's models never populated the dropdown."""
        called = {}

        async def fake_llamacpp_fetch(host, headers=None):
            called["host"] = host
            return ["gemma-3-4b"]

        async def fail_ollama_fetch(host, headers=None):
            raise AssertionError("must not call Ollama's fetcher for backend=llamacpp")

        monkeypatch.setattr(
            "comfydv._llm.llamacpp_provider._fetch_models", fake_llamacpp_fetch
        )
        monkeypatch.setattr("comfydv.ollama._fetch_models", fail_ollama_fetch)

        data, status = self._call(
            {"host": "http://localhost:8080", "backend": "llamacpp"}
        )

        assert status == 200
        assert data == {"models": ["gemma-3-4b"]}
        assert called["host"] == "http://localhost:8080"

    def test_no_models_returns_503(self, monkeypatch):
        async def fake_fetch(host, headers=None):
            return []

        monkeypatch.setattr("comfydv.ollama._fetch_models", fake_fetch)
        data, status = self._call({"host": "http://localhost:11434"})

        assert status == 503
        assert "error" in data


class TestUpdateStructuredOutputsRoute:
    def teardown_method(self):
        # This route mutates ChatCompletion's class-level RETURN_TYPES
        # directly (same mechanism as chat()'s update_outputs call) — reset
        # so it doesn't leak into other tests. The autouse conftest fixture
        # only resets around chat()-driven tests within the same test; this
        # class calls the route function directly, bypassing that fixture's
        # normal per-test boundary, so reset explicitly here too for safety.
        ChatCompletion.RETURN_TYPES = ChatCompletion._BASE_RETURN_TYPES
        ChatCompletion.RETURN_NAMES = ChatCompletion._BASE_RETURN_NAMES
        ChatCompletion.node_configs.clear()

    def _call(self, body: dict) -> dict:
        import comfydv.ollama as ollama_mod
        from comfydv._llm.ollama_provider import _run_async

        resp = _run_async(
            ollama_mod._update_structured_outputs_endpoint(_FakeRequest(body))
        )
        return json.loads(resp.text)

    def test_structured_output_false_returns_base_outputs(self):
        data = self._call(
            {"unique_id": "r1", "structured_output": False, "output_schema": "{}"}
        )
        assert [o["name"] for o in data["outputs"]] == [
            "response",
            "updated_history",
            "model_name",
        ]

    def test_valid_schema_returns_dynamic_outputs(self):
        data = self._call(
            {
                "unique_id": "r2",
                "structured_output": True,
                "output_schema": _MULTI_FIELD_SCHEMA,
            }
        )
        names = [o["name"] for o in data["outputs"]]
        types = [o["type"] for o in data["outputs"]]
        assert names == [
            "response",
            "updated_history",
            "model_name",
            "summary",
            "score",
            "is_positive",
        ]
        assert types == [
            "STRING",
            "OLLAMA_HISTORY",
            "STRING",
            "STRING",
            "INT",
            "BOOLEAN",
        ]

    def test_invalid_json_while_typing_falls_back_to_base_outputs(self):
        """Mid-keystroke output_schema (e.g. '{"type": "obj') must not error
        the route — it should just report the base outputs until the JSON
        becomes valid again."""
        data = self._call(
            {
                "unique_id": "r3",
                "structured_output": True,
                "output_schema": '{"type": "obj',
            }
        )
        assert [o["name"] for o in data["outputs"]] == [
            "response",
            "updated_history",
            "model_name",
        ]

    def test_incomplete_schema_missing_properties_falls_back_to_base_outputs(self):
        data = self._call(
            {
                "unique_id": "r4",
                "structured_output": True,
                "output_schema": '{"type": "object"}',
            }
        )
        assert [o["name"] for o in data["outputs"]] == [
            "response",
            "updated_history",
            "model_name",
        ]

    def test_response_reflects_class_state_not_just_this_call(self):
        """RETURN_TYPES/RETURN_NAMES are class-level (see ADR/update_outputs
        docstring) — the route must report the actual resulting class state,
        not just echo back what was requested."""
        self._call(
            {
                "unique_id": "r5",
                "structured_output": True,
                "output_schema": _SINGLE_FIELD_SCHEMA,
            }
        )
        assert ChatCompletion.RETURN_NAMES[-1] == "output"

        data = self._call(
            {"unique_id": "r5", "structured_output": False, "output_schema": "{}"}
        )
        assert [o["name"] for o in data["outputs"]] == [
            "response",
            "updated_history",
            "model_name",
        ]
        assert ChatCompletion.RETURN_NAMES == ChatCompletion._BASE_RETURN_NAMES


# ---------------------------------------------------------------------------
# US4 (ADR-007) — migration mapping
# ---------------------------------------------------------------------------


class TestMigrationMap:
    def test_every_renamed_node_and_socket_has_a_documented_replacement(self):
        assert MIGRATION_MAP == {
            "OllamaChatCompletion": "ChatCompletion",
            "OllamaModelSelector": "LLMModelSelector",
            "OllamaLoadModel": "LLMLoadModel",
            "OllamaUnloadModel": "LLMUnloadModel",
            "OLLAMA_CLIENT": "LLM_CLIENT",
        }


# ---------------------------------------------------------------------------
# Node contract sanity checks (ComfyUI registration requirements)
# ---------------------------------------------------------------------------


class TestNodeContracts:
    """Every node must satisfy ComfyUI's node registration contract."""

    NODE_CLASSES = [
        OllamaClient,
        LLMModelSelector,
        LLMLoadModel,
        LLMUnloadModel,
        ChatCompletion,
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


# ---------------------------------------------------------------------------
# US1 (spec 009) — Image input on ChatCompletion
#   features/us1_describe_image.feature
# ---------------------------------------------------------------------------


class TestUS1ImageEncode:
    """_encode_image_tensor(): ComfyUI IMAGE tensor -> base64 PNG(s)."""

    def test_encode_single_image_returns_decodable_png(self):
        import base64
        import io

        import torch
        from PIL import Image

        from comfydv.ollama import _encode_image_tensor

        # ComfyUI IMAGE: [B, H, W, C] float 0..1
        img = torch.zeros(1, 4, 8, 3)
        img[0, :, :, 0] = 1.0  # solid red

        out = _encode_image_tensor(img)

        assert isinstance(out, list)
        assert len(out) == 1
        pil = Image.open(io.BytesIO(base64.b64decode(out[0])))
        assert pil.format == "PNG"
        assert pil.size == (8, 4)  # PIL size is (W, H)
        assert pil.convert("RGB").getpixel((0, 0)) == (255, 0, 0)

    def test_encode_batch_returns_one_base64_per_frame(self):
        import torch

        from comfydv.ollama import _encode_image_tensor

        img = torch.zeros(3, 4, 8, 3)
        out = _encode_image_tensor(img)
        assert len(out) == 3

    def test_encode_none_returns_empty_list(self):
        from comfydv.ollama import _encode_image_tensor

        assert _encode_image_tensor(None) == []

    def test_encode_empty_batch_returns_empty_list(self):
        import torch

        from comfydv.ollama import _encode_image_tensor

        assert _encode_image_tensor(torch.zeros(0, 4, 8, 3)) == []


class TestUS1ImageInputNode:
    """ChatCompletion optional IMAGE input attaches to the current user turn."""

    def _last_messages(self, fake):
        # _FakeProvider records ("chat", model, messages, options, timeout, retries)
        chat_calls = [c for c in fake.calls if c[0] == "chat"]
        return chat_calls[-1][2]

    def test_chat_completion_has_optional_image_input(self):
        inputs = ChatCompletion.INPUT_TYPES()
        assert "image" in inputs["optional"], (
            "ChatCompletion must expose an optional IMAGE input for VLM use"
        )
        assert inputs["optional"]["image"][0] == "IMAGE"

    def test_chat_completion_image_input_is_not_required(self):
        inputs = ChatCompletion.INPUT_TYPES()
        assert "image" not in inputs.get("required", {})

    def test_return_positions_unchanged_by_image_input(self):
        # Constitution VI: outputs untouched — only an optional input is added.
        assert ChatCompletion.RETURN_TYPES[:2] == ("STRING", "OLLAMA_HISTORY")
        assert ChatCompletion.RETURN_NAMES[:2] == ("response", "updated_history")

    def test_wired_image_attaches_to_last_user_message(self):
        import torch

        fake = _FakeProvider(chat_response="a red square")
        img = torch.zeros(1, 4, 8, 3)
        img[0, :, :, 0] = 1.0

        ChatCompletion().chat(client=fake, model="m", prompt="describe", image=img)

        messages = self._last_messages(fake)
        assert messages[-1].role == "user"
        assert messages[-1].content == "describe"
        assert messages[-1].images and len(messages[-1].images) == 1

    def test_unwired_image_leaves_messages_text_only(self):
        fake = _FakeProvider(chat_response="ok")
        ChatCompletion().chat(client=fake, model="m", prompt="hi")
        messages = self._last_messages(fake)
        assert messages[-1].images is None

    def test_image_not_added_to_history_turns(self):
        import torch

        fake = _FakeProvider(chat_response="ok")
        img = torch.zeros(1, 2, 2, 3)
        history = [
            {"role": "user", "content": "earlier q"},
            {"role": "assistant", "content": "earlier a"},
        ]

        ChatCompletion().chat(
            client=fake, model="m", prompt="now", history=history, image=img
        )

        messages = self._last_messages(fake)
        # Every turn except the final user turn must carry no image (FR-007).
        assert all(m.images is None for m in messages[:-1])
        assert messages[-1].content == "now"
        assert messages[-1].images and len(messages[-1].images) == 1
