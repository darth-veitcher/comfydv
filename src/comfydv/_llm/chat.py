"""Shared chat_structured() helper — pydantic-ai backed structured output.

Used by every ``LLMProvider`` implementation's ``chat_structured()`` method
(ADR-007) so Ollama and llama.cpp share one implementation of tool-calling/
structured-output logic instead of each hand-rolling it, since both speak
OpenAI-compatible ``/v1/chat/completions``.

Ports ADR-006's retry/validation contract exactly: bounded retries (0-5,
clamped), and a ``RuntimeError`` naming the model, attempt count, and a
truncated snippet of the last invalid response on exhausted retries. The
Agent's own internal retries are disabled (``retries=0``) — this helper
drives its own retry loop so the error contract is comfydv's, not
pydantic-ai's internal one.
"""

import asyncio
from typing import cast

from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry, UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from .provider import Message
from .retry import RETRY_BACKOFF_SECS, next_seed

_STRUCTURED_OUTPUT_FAILURE_EXCEPTIONS = (
    UnexpectedModelBehavior,
    ModelRetry,
    ValidationError,
)


def _build_agent(
    *,
    base_url: str,
    model: str,
    schema: type[BaseModel],
    headers: dict | None,
    timeout_secs: float,
) -> Agent:
    import httpx

    http_client = httpx.AsyncClient(
        headers=headers or None, timeout=httpx.Timeout(timeout_secs)
    )
    provider = OpenAIProvider(
        base_url=base_url, api_key="not-needed", http_client=http_client
    )
    chat_model = OpenAIChatModel(model, provider=provider)
    return Agent(chat_model, output_type=schema, retries=0)


def _history_to_messages(messages: list[Message]) -> list:
    """Convert all but the last message into pydantic-ai's typed history.

    The last message (the current turn) is passed separately as
    ``Agent.run()``'s ``user_prompt`` — see ``chat_structured()``.
    """
    history: list = []
    for msg in messages[:-1]:
        if msg.role == "assistant":
            history.append(ModelResponse(parts=[TextPart(msg.content)]))
        elif msg.role == "system":
            history.append(ModelRequest(parts=[SystemPromptPart(msg.content)]))
        else:
            history.append(ModelRequest(parts=[UserPromptPart(msg.content)]))
    return history


async def chat_structured(
    *,
    base_url: str,
    model: str,
    messages: list[Message],
    schema: type[BaseModel],
    headers: dict | None = None,
    options: dict | None = None,
    max_retries: int = 2,
    timeout_secs: float = 300.0,
) -> BaseModel:
    """Call ``model`` at ``base_url`` (an OpenAI-compatible ``/v1`` root) and
    return a validated instance of ``schema``.

    ``options`` is forwarded verbatim as a top-level ``"options"`` field in
    the request body via pydantic-ai's ``extra_body`` — the same shape the
    pre-ADR-007 hand-rolled implementation sent, so provider-native sampling
    params (Ollama's ``num_predict``/``repeat_penalty``/etc., set via the
    ``OllamaOption*`` nodes) keep working unchanged rather than being
    lossily remapped onto pydantic-ai's own standardized ``ModelSettings``
    fields.

    Retries up to ``max_retries`` times (clamped 0-5) on validation failure
    before raising ``RuntimeError``. Never returns a value that failed
    validation against ``schema``.
    """
    if not messages or messages[-1].role != "user":
        raise ValueError(
            "chat_structured requires the last message to have role='user'"
        )

    agent = _build_agent(
        base_url=base_url,
        model=model,
        schema=schema,
        headers=headers,
        timeout_secs=timeout_secs,
    )
    history = _history_to_messages(messages)
    prompt = messages[-1].content
    model_settings: ModelSettings | None = (
        {"extra_body": {"options": options}} if options else None
    )

    total_attempts = max(0, min(int(max_retries), 5)) + 1
    last_error: Exception | None = None
    last_invalid_text = ""
    for attempt in range(1, total_attempts + 1):
        attempt_settings = dict(model_settings) if model_settings else {}
        if attempt > 1:
            # Confirmed live: a freshly-loaded model's first structured-output
            # attempt can fail outright (no valid tool call at all) and then
            # behave normally on the very next call. Retrying with the exact
            # same request reproduces the same failure if the model is
            # genuinely stuck rather than just unlucky, so force a new seed
            # (pydantic-ai maps ModelSettings["seed"] to the OpenAI API's
            # top-level "seed" param, which works against both Ollama's and
            # llama-server's OpenAI-compatible endpoints) and give it a beat
            # via RETRY_BACKOFF_SECS in case it's still finishing loading.
            attempt_settings["seed"] = next_seed(options, attempt)
        try:
            result = await agent.run(
                prompt,
                message_history=history,
                model_settings=cast(ModelSettings, attempt_settings)
                if attempt_settings
                else None,
            )
            # agent's output_type is the caller's `schema` (a runtime value,
            # not a static type parameter), so the checker can't narrow
            # result.output past Agent's default `str` — cast to the
            # function's declared return type, which schema is a subtype of.
            return cast(BaseModel, result.output)
        except _STRUCTURED_OUTPUT_FAILURE_EXCEPTIONS as exc:
            last_error = exc
            last_invalid_text = str(exc)
            if attempt < total_attempts:
                await asyncio.sleep(RETRY_BACKOFF_SECS)

    raise RuntimeError(
        f"chat_structured: response failed validation against schema after "
        f"{total_attempts} attempt(s) (model={model!r}). Last error: "
        f"{last_error}. Last response (truncated): {last_invalid_text[:300]!r}"
    )
