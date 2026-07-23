"""
Tests for comfydv._llm.chat.chat_structured — shared pydantic-ai backed
structured output, used by every LLMProvider implementation (ADR-007).

Mocks at the comfydv._llm.chat._build_agent seam (returns a fake agent
exposing an async .run()), mirroring test_ollama.py's existing convention
of monkeypatching the module-level HTTP seam rather than the network itself.
Uses _run_async (same helper comfydv.ollama uses) to drive the coroutine
synchronously, matching this project's existing test style rather than
introducing a pytest-asyncio dependency.

BDD coverage:
  ../specs/007-llm-provider-abstraction/features/us2_structured_output.feature
"""

from dataclasses import dataclass

import pytest
from pydantic import BaseModel, ValidationError

import comfydv._llm.chat as chat_mod
from comfydv._llm.ollama_provider import _run_async
from comfydv._llm.provider import Message


@pytest.fixture(autouse=True)
def _no_retry_backoff(monkeypatch):
    """Keep the real RETRY_BACKOFF_SECS delay out of this suite's wall-clock
    time for every test except the ones that specifically assert on it
    (which re-monkeypatch locally, overriding this)."""

    async def _instant_sleep(_secs):
        pass

    monkeypatch.setattr(chat_mod.asyncio, "sleep", _instant_sleep)


class _Widget(BaseModel):
    name: str
    count: int


@dataclass
class _FakeResult:
    output: object


class _FakeAgent:
    """Stand-in for pydantic_ai.Agent — .run() is scripted per test."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def run(self, prompt, *, message_history=None, model_settings=None):
        self.calls.append((prompt, message_history, model_settings))
        outcome = self._responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _FakeResult(output=outcome)


def _messages(*, system=None, history=None, prompt="hi"):
    msgs = []
    if system:
        msgs.append(Message(role="system", content=system))
    for role, content in history or []:
        msgs.append(Message(role=role, content=content))
    msgs.append(Message(role="user", content=prompt))
    return msgs


def test_chat_structured_returns_validated_output(monkeypatch):
    fake = _FakeAgent([_Widget(name="a", count=1)])
    monkeypatch.setattr(chat_mod, "_build_agent", lambda **kw: fake)

    result = _run_async(
        chat_mod.chat_structured(
            base_url="http://localhost:11434/v1",
            model="llama3",
            messages=_messages(prompt="describe a widget"),
            schema=_Widget,
        )
    )

    assert result == _Widget(name="a", count=1)
    assert fake.calls[0][0] == "describe a widget"


def test_chat_structured_retries_on_validation_failure(monkeypatch):
    bad = ValidationError.from_exception_data("Widget", [])
    fake = _FakeAgent([bad, _Widget(name="b", count=2)])
    monkeypatch.setattr(chat_mod, "_build_agent", lambda **kw: fake)

    result = _run_async(
        chat_mod.chat_structured(
            base_url="http://localhost:11434/v1",
            model="llama3",
            messages=_messages(),
            schema=_Widget,
            max_retries=2,
        )
    )

    assert result == _Widget(name="b", count=2)
    assert len(fake.calls) == 2


def test_chat_structured_exhausted_retries_raises_runtime_error(monkeypatch):
    bad = ValidationError.from_exception_data("Widget", [])
    fake = _FakeAgent([bad, bad, bad])  # max_retries=2 -> 3 total attempts
    monkeypatch.setattr(chat_mod, "_build_agent", lambda **kw: fake)

    with pytest.raises(RuntimeError) as exc_info:
        _run_async(
            chat_mod.chat_structured(
                base_url="http://localhost:11434/v1",
                model="llama3",
                messages=_messages(),
                schema=_Widget,
                max_retries=2,
            )
        )

    message = str(exc_info.value)
    assert "llama3" in message
    assert "3 attempt(s)" in message
    assert len(fake.calls) == 3


def test_chat_structured_max_retries_clamped_to_five(monkeypatch):
    bad = ValidationError.from_exception_data("Widget", [])
    fake = _FakeAgent([bad] * 6)
    monkeypatch.setattr(chat_mod, "_build_agent", lambda **kw: fake)

    with pytest.raises(RuntimeError, match=r"6 attempt\(s\)"):
        _run_async(
            chat_mod.chat_structured(
                base_url="http://localhost:11434/v1",
                model="llama3",
                messages=_messages(),
                schema=_Widget,
                max_retries=999,  # clamped to 5 -> 6 total attempts
            )
        )
    assert len(fake.calls) == 6


def test_chat_structured_forwards_options_as_extra_body(monkeypatch):
    """Regression guard: options (Ollama-native sampling params set via the
    OllamaOption* nodes — temperature, seed, num_predict, repeat_penalty,
    etc.) must reach the request, not be silently dropped in structured
    mode. Forwarded verbatim via pydantic-ai's model_settings.extra_body,
    matching the pre-ADR-007 payload shape exactly (no lossy remapping onto
    ModelSettings' own standardized field names)."""
    fake = _FakeAgent([_Widget(name="a", count=1)])
    monkeypatch.setattr(chat_mod, "_build_agent", lambda **kw: fake)

    _run_async(
        chat_mod.chat_structured(
            base_url="http://localhost:11434/v1",
            model="llama3",
            messages=_messages(),
            schema=_Widget,
            options={"temperature": 0.0, "seed": 42, "num_predict": 128},
        )
    )

    assert fake.calls[0][2] == {
        "extra_body": {"options": {"temperature": 0.0, "seed": 42, "num_predict": 128}}
    }


def test_chat_structured_no_options_means_no_model_settings(monkeypatch):
    fake = _FakeAgent([_Widget(name="a", count=1)])
    monkeypatch.setattr(chat_mod, "_build_agent", lambda **kw: fake)

    _run_async(
        chat_mod.chat_structured(
            base_url="http://localhost:11434/v1",
            model="llama3",
            messages=_messages(),
            schema=_Widget,
        )
    )

    assert fake.calls[0][2] is None


def test_chat_structured_requires_last_message_user_role():
    with pytest.raises(ValueError, match="role='user'"):
        _run_async(
            chat_mod.chat_structured(
                base_url="http://localhost:11434/v1",
                model="llama3",
                messages=[Message(role="system", content="only a system message")],
                schema=_Widget,
            )
        )


# ---------------------------------------------------------------------------
# retry-on-failure seed/backoff — live-verified: a freshly-loaded model's
# first structured-output attempt can fail outright, then behave normally on
# the very next call.
# ---------------------------------------------------------------------------


def test_chat_structured_retry_injects_incrementing_seed(monkeypatch):
    bad = ValidationError.from_exception_data("Widget", [])
    fake = _FakeAgent([bad, bad, _Widget(name="c", count=3)])
    monkeypatch.setattr(chat_mod, "_build_agent", lambda **kw: fake)

    _run_async(
        chat_mod.chat_structured(
            base_url="http://localhost:11434/v1",
            model="llama3",
            messages=_messages(),
            schema=_Widget,
            max_retries=2,
        )
    )

    assert fake.calls[0][2] is None  # attempt 1 untouched — no options set
    assert fake.calls[1][2]["seed"] == 1
    assert fake.calls[2][2]["seed"] == 2


def test_chat_structured_retry_seed_starts_from_pinned_base(monkeypatch):
    bad = ValidationError.from_exception_data("Widget", [])
    fake = _FakeAgent([bad, _Widget(name="c", count=3)])
    monkeypatch.setattr(chat_mod, "_build_agent", lambda **kw: fake)

    _run_async(
        chat_mod.chat_structured(
            base_url="http://localhost:11434/v1",
            model="llama3",
            messages=_messages(),
            schema=_Widget,
            options={"seed": 42},
            max_retries=2,
        )
    )

    assert fake.calls[0][2] == {"extra_body": {"options": {"seed": 42}}}
    assert fake.calls[1][2]["seed"] == 43  # base(42) + (attempt 2 - 1)
    # The nested Ollama-native options.seed must track the same retry seed as
    # the top-level one — a backend that honors the nested field over the
    # top-level OpenAI "seed" must not keep seeing the stale pinned value.
    assert fake.calls[1][2]["extra_body"] == {"options": {"seed": 43}}


def test_chat_structured_retry_does_not_mutate_callers_options_dict(monkeypatch):
    """Regression guard for the fix above: syncing the nested seed must copy,
    not mutate, the caller's options dict — otherwise a second call reusing
    the same options object would start from the wrong base seed."""
    bad = ValidationError.from_exception_data("Widget", [])
    fake = _FakeAgent([bad, _Widget(name="c", count=3)])
    monkeypatch.setattr(chat_mod, "_build_agent", lambda **kw: fake)

    caller_options = {"seed": 42}
    _run_async(
        chat_mod.chat_structured(
            base_url="http://localhost:11434/v1",
            model="llama3",
            messages=_messages(),
            schema=_Widget,
            options=caller_options,
            max_retries=2,
        )
    )

    assert caller_options == {"seed": 42}


def test_chat_structured_retry_sleeps_between_attempts(monkeypatch):
    sleep_calls = []

    async def fake_sleep(secs):
        sleep_calls.append(secs)

    monkeypatch.setattr(chat_mod.asyncio, "sleep", fake_sleep)

    bad = ValidationError.from_exception_data("Widget", [])
    fake = _FakeAgent([bad, _Widget(name="c", count=3)])
    monkeypatch.setattr(chat_mod, "_build_agent", lambda **kw: fake)

    _run_async(
        chat_mod.chat_structured(
            base_url="http://localhost:11434/v1",
            model="llama3",
            messages=_messages(),
            schema=_Widget,
            max_retries=2,
        )
    )

    assert sleep_calls == [chat_mod.RETRY_BACKOFF_SECS]


def test_history_to_messages_preserves_order_and_roles():
    from pydantic_ai.messages import ModelRequest, ModelResponse

    msgs = _messages(
        system="be terse",
        history=[("user", "first"), ("assistant", "reply")],
        prompt="second",
    )
    history = chat_mod._history_to_messages(msgs)

    # system, user(first), assistant(reply) — "second" is excluded (it's the
    # current turn, passed separately as Agent.run()'s user_prompt).
    assert len(history) == 3
    assert isinstance(history[0], ModelRequest)  # system
    assert isinstance(history[1], ModelRequest)  # user
    assert isinstance(history[2], ModelResponse)  # assistant


# ---------------------------------------------------------------------------
# Image input (spec 009, US3; features/us3_structured_image.feature)
# ---------------------------------------------------------------------------


def test_chat_structured_attaches_image_to_user_prompt(monkeypatch):
    """The current turn's image rides on Agent.run()'s user_prompt as a
    pydantic-ai BinaryContent (ADR-008, research.md Decision 1)."""
    import base64

    from pydantic_ai.messages import BinaryContent

    fake = _FakeAgent([_Widget(name="sq", count=1)])
    monkeypatch.setattr(chat_mod, "_build_agent", lambda **kw: fake)
    b64 = base64.b64encode(b"PNGDATA").decode()

    _run_async(
        chat_mod.chat_structured(
            base_url="http://x/v1",
            model="m",
            schema=_Widget,
            messages=[Message(role="user", content="describe", images=[b64])],
        )
    )

    prompt = fake.calls[0][0]
    assert isinstance(prompt, list)
    assert prompt[0] == "describe"
    assert isinstance(prompt[1], BinaryContent)
    assert prompt[1].data == b"PNGDATA"
    assert prompt[1].media_type == "image/png"


def test_chat_structured_text_only_prompt_is_plain_string(monkeypatch):
    """FR-003: an image-less structured call is unchanged — plain-string
    user_prompt, exactly as before spec 009."""
    fake = _FakeAgent([_Widget(name="a", count=1)])
    monkeypatch.setattr(chat_mod, "_build_agent", lambda **kw: fake)

    _run_async(
        chat_mod.chat_structured(
            base_url="http://x/v1",
            model="m",
            schema=_Widget,
            messages=[Message(role="user", content="hi")],
        )
    )

    assert fake.calls[0][0] == "hi"


def test_chat_structured_attaches_image_to_history_user_turn(monkeypatch):
    """A prior user turn that carried an image keeps it in message_history."""
    import base64

    from pydantic_ai.messages import BinaryContent, UserPromptPart

    fake = _FakeAgent([_Widget(name="a", count=1)])
    monkeypatch.setattr(chat_mod, "_build_agent", lambda **kw: fake)
    b64 = base64.b64encode(b"IMG").decode()
    msgs = [
        Message(role="user", content="earlier", images=[b64]),
        Message(role="assistant", content="ok"),
        Message(role="user", content="now"),
    ]

    _run_async(
        chat_mod.chat_structured(
            base_url="http://x/v1", model="m", schema=_Widget, messages=msgs
        )
    )

    history = fake.calls[0][1]
    part = history[0].parts[0]
    assert isinstance(part, UserPromptPart)
    assert isinstance(part.content, list)
    assert part.content[0] == "earlier"
    assert isinstance(part.content[1], BinaryContent)
    assert part.content[1].data == b"IMG"
