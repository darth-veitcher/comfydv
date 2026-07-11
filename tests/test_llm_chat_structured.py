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

    async def run(self, prompt, *, message_history=None):
        self.calls.append((prompt, message_history))
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
