"""
Tests for comfydv._llm — shared LLMProvider protocol and OllamaProvider.

Test layers:
  Unit (no marker)             — pure Python, no live services
  Integration (-m integration) — requires live Ollama at localhost:11434

BDD coverage:
  ../specs/007-llm-provider-abstraction/features/us1_connect_and_chat.feature
  ../specs/007-llm-provider-abstraction/features/us2_structured_output.feature
  ../specs/007-llm-provider-abstraction/features/us3_model_lifecycle.feature
"""

from comfydv._llm.ollama_provider import OllamaProvider
from comfydv._llm.provider import Message, ModelInfo, ModelStatus


def test_ollama_provider_captures_connection_state():
    provider = OllamaProvider("http://localhost:11434", headers={"X-Test": "1"})
    assert provider.host == "http://localhost:11434"
    assert provider.headers == {"X-Test": "1"}


def test_ollama_provider_headers_default_to_none():
    provider = OllamaProvider("http://localhost:11434")
    assert provider.headers is None


def test_model_status_values():
    assert ModelStatus.LOADED == "loaded"
    assert ModelStatus.SLEEPING == "sleeping"
    assert ModelStatus.DOWNLOADING == "downloading"


def test_model_info_optional_size():
    info = ModelInfo(name="llama3", status=ModelStatus.UNLOADED)
    assert info.size is None


def test_message_roles():
    Message(role="system", content="be terse")
    Message(role="user", content="hi")
    Message(role="assistant", content="hello")
