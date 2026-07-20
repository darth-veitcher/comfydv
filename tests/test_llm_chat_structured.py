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
    assert fake.calls[1][2]["extra_body"] == {"options": {"seed": 42}}


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
