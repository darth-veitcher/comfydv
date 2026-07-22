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


# --- US1 foundational: Message.images carrier (spec 009, contract T1) ---


def test_message_images_defaults_to_none():
    """A text-only turn carries no images."""
    msg = Message(role="user", content="hi")
    assert msg.images is None


def test_message_images_round_trips_base64_list():
    msg = Message(role="user", content="describe", images=["aGVsbG8=", "d29ybGQ="])
    assert msg.images == ["aGVsbG8=", "d29ybGQ="]


def test_message_text_only_dump_omits_images_key():
    """FR-003/SC-004: an image-less message must serialize byte-identically to
    today — no stray ``images`` key in the transport payload."""
    msg = Message(role="user", content="hi")
    assert msg.model_dump(exclude_none=True) == {"role": "user", "content": "hi"}


def test_message_with_images_dump_includes_images_key():
    msg = Message(role="user", content="describe", images=["aGVsbG8="])
    dumped = msg.model_dump(exclude_none=True)
    assert dumped == {
        "role": "user",
        "content": "describe",
        "images": ["aGVsbG8="],
    }
