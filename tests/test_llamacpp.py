"""
Tests for comfydv.llamacpp.LlamaCppClient — the one new ComfyUI node this
feature introduces. Also proves the adapter pattern end-to-end (US4): the
same generic nodes work unmodified against either provider.

BDD coverage:
  ../specs/008-llamacpp-integration/features/us1_connect_and_chat.feature
  ../specs/008-llamacpp-integration/features/us4_swap_backends.feature
"""

from comfydv._llm.llamacpp_provider import LlamaCppProvider
from comfydv._llm.ollama_provider import OllamaProvider
from comfydv.llamacpp import LlamaCppClient
from comfydv.ollama import (
    ChatCompletion,
    LLMLoadModel,
    LLMModelSelector,
    LLMUnloadModel,
)


class _FakeProvider:
    """Mirrors tests/test_ollama.py's _FakeProvider — reused here for US4's
    swap-backends proof rather than duplicated, since the whole point is
    that node behavior doesn't depend on which concrete provider it gets."""

    def __init__(self, chat_response="ok"):
        self.chat_response = chat_response
        self.models = [{"name": "m", "status": "loaded"}]
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
        self.calls.append(("chat", model))
        return self.chat_response


def test_client_outputs_llamacpp_provider():
    (client,) = LlamaCppClient().create_client("http://localhost:8080")
    assert isinstance(client, LlamaCppProvider)
    assert client.host == "http://localhost:8080"


def test_client_default_host_matches_llama_server_default_port():
    input_types = LlamaCppClient.INPUT_TYPES()
    assert input_types["required"]["host"][1]["default"] == "http://localhost:8080"


def test_client_output_type_is_generic_llm_client():
    assert LlamaCppClient.RETURN_TYPES == ("LLM_CLIENT",)


def test_client_carries_headers():
    (client,) = LlamaCppClient().create_client(
        "http://localhost:8080", headers={"Authorization": "Bearer abc"}
    )
    assert client.headers == {"Authorization": "Bearer abc"}


def test_node_contract():
    assert hasattr(LlamaCppClient, "INPUT_TYPES")
    assert hasattr(LlamaCppClient, "RETURN_TYPES")
    assert hasattr(LlamaCppClient, "FUNCTION")
    assert hasattr(LlamaCppClient, "CATEGORY")
    assert hasattr(LlamaCppClient, LlamaCppClient.FUNCTION)


def test_registered_in_node_class_mappings():
    from comfydv import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

    assert NODE_CLASS_MAPPINGS["LlamaCppClient"] is LlamaCppClient
    assert "LlamaCppClient" in NODE_DISPLAY_NAME_MAPPINGS


# ---------------------------------------------------------------------------
# US4 — swap backends without touching downstream nodes
# ---------------------------------------------------------------------------


def _run_workflow(client) -> None:
    """The same node sequence a workflow author would wire up, regardless
    of which provider `client` is."""
    ChatCompletion().chat(client=client, model="m", prompt="hi")
    LLMModelSelector().select_model(client=client, model="m")
    LLMLoadModel().load_model(client=client, model="m")
    LLMUnloadModel().unload_model(client=client, model="m")


def test_same_workflow_runs_against_either_fake_provider():
    """No node branches on provider type — the same call sequence succeeds
    whether client looks like an Ollama-shaped or llama.cpp-shaped provider."""
    ollama_like = _FakeProvider(chat_response="ollama says hi")
    llamacpp_like = _FakeProvider(chat_response="llamacpp says hi")

    # Neither call raises — that's the actual assertion. If ChatCompletion/
    # LLMModelSelector/LLMLoadModel/LLMUnloadModel secretly special-cased a
    # concrete provider type (isinstance checks, attribute probing beyond
    # the protocol), one of these would fail.
    _run_workflow(ollama_like)
    _run_workflow(llamacpp_like)

    # LLMModelSelector is pure passthrough (client is accepted only for
    # wiring/typing, never dereferenced), so it makes no provider call.
    expected = ["chat", "load_model", "unload_model"]
    assert [c[0] for c in ollama_like.calls] == expected
    assert [c[0] for c in llamacpp_like.calls] == expected


def test_real_providers_are_interchangeable_client_output():
    """OllamaClient and LlamaCppClient both emit LLM_CLIENT — a workflow
    author can wire either one into the same downstream nodes."""
    from comfydv.ollama import OllamaClient

    (ollama_client,) = OllamaClient().create_client("http://localhost:11434")
    (llamacpp_client,) = LlamaCppClient().create_client("http://localhost:8080")

    assert isinstance(ollama_client, OllamaProvider)
    assert isinstance(llamacpp_client, LlamaCppProvider)
    # Both satisfy the same protocol shape — same method names available.
    for method in (
        "list_models",
        "load_model",
        "unload_model",
        "chat",
        "chat_structured",
    ):
        assert callable(getattr(ollama_client, method))
        assert callable(getattr(llamacpp_client, method))
