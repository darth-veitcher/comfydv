"""Shared chat_structured() helper — pydantic-ai backed structured output.

Used by ``LlamaCppProvider.chat_structured()`` (ADR-007) over llama-server's
OpenAI-compatible ``/v1/chat/completions``. ``OllamaProvider`` no longer uses
this module (ADR-009): Ollama's OpenAI-compatible endpoint was found to
silently reload the model at its default context size on every call,
discarding any ``options.num_ctx`` override even when included in that same
request — a behavior specific to Ollama's compat layer, not llama-server's.
``OllamaProvider.chat_structured()`` now hand-rolls its own structured-output
call over Ollama's *native* ``/api/chat`` + ``"format"``, which doesn't have
that problem.

ADR-009: the Agent uses ``NativeOutput`` (``response_format``/JSON-schema
constrained decoding), not pydantic-ai's default tool-calling. Live-tested
against a "thinking"-capable model: tool-calling let the model spend its
whole token budget on chain-of-thought reasoning and never emit the tool
call; native output keeps reasoning in a separate response field and the
constrained ``content`` always comes back as schema-valid JSON. This benefit
still applies to llama.cpp, which is why this module (and its NativeOutput
choice) is kept for that provider.

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
from pydantic_ai import Agent, NativeOutput
from pydantic_ai.exceptions import ModelRetry, UnexpectedModelBehavior
from pydantic_ai.messages import (
    BinaryContent,
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
from .retry import (
    RETRY_BACKOFF_SECS,
    EmbedFn,
    is_refusal,
    next_seed,
    next_timeout_secs,
    record_attempt_info,
)

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
    return Agent(chat_model, output_type=NativeOutput(schema), retries=0)


def _user_prompt_content(msg: Message):
    """Render a user turn as pydantic-ai user-prompt content.

    Text-only ``msg`` → the plain ``content`` string, byte-identical to the
    pre-009 path (FR-003). A turn carrying images → ``[content, *images]``
    where each image is a ``BinaryContent`` PNG (ADR-008 / research.md
    Decision 1); ``OpenAIChatModel`` renders these as OpenAI ``image_url``
    parts, so both backends reach the same multimodal request through one
    shared code path.
    """
    if not msg.images:
        return msg.content
    import base64

    content: list = [msg.content]
    for image in msg.images:
        content.append(
            BinaryContent(data=base64.b64decode(image), media_type="image/png")
        )
    return content


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
            history.append(
                ModelRequest(parts=[UserPromptPart(_user_prompt_content(msg))])
            )
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
    embed_fn: EmbedFn | None = None,
    attempt_info: dict | None = None,
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

    ADR-010: ``options`` may also carry a ``"think"`` key (bool), popped out
    here rather than forwarded inside the nested ``options`` object —
    llama-server's OpenAI-compatible endpoint doesn't recognize a literal
    ``"think"`` key there. Translated to its own two documented
    request-body toggles instead: ``chat_template_kwargs:
    {"enable_thinking": ...}`` (Qwen3-style models) and, when disabling,
    ``reasoning_effort: "none"`` (the more model-agnostic OpenAI convention
    llama-server also honors) — both via ``extra_body`` the same way
    ``options`` is. This provider only serves ``LlamaCppProvider`` — see
    ``OllamaProvider``'s own hand-rolled ``chat_structured`` for why Ollama
    needed a different mechanism entirely. Sourced from llama.cpp's server
    docs, not live-verified against a running llama-server (no instance
    available at implementation time) — verify against your own deployment.

    Retries up to ``max_retries`` times (clamped 0-5) on validation failure
    before raising ``RuntimeError``. Never returns a value that failed
    validation against ``schema``.

    ``options`` may also carry a ``"refusal_retry"`` config dict (same
    comfydv-level convention as ``"think"``, emitted by
    ``OllamaOptionRefusalRetry``) — a detected refusal/deflection (see
    ``_llm/retry.py``) is treated exactly like a validation failure: retried
    with a bumped seed rather than returned to the caller. ``embed_fn`` is
    ``LlamaCppProvider``'s own ``embed()``, bound to whatever embedding
    model the config names — passed in rather than looked up here since
    this module has no provider instance of its own to call.
    """
    if not messages or messages[-1].role != "user":
        raise ValueError(
            "chat_structured requires the last message to have role='user'"
        )

    history = _history_to_messages(messages)
    prompt = _user_prompt_content(messages[-1])
    think = None
    if options and "think" in options:
        options = dict(options)
        think = options.pop("think")
        options = options or None
    refusal_cfg = None
    if options and "refusal_retry" in options:
        options = dict(options)
        refusal_cfg = options.pop("refusal_retry")
        options = options or None
    extra_body: dict = {}
    if options:
        extra_body["options"] = options
    if think is not None:
        extra_body["chat_template_kwargs"] = {"enable_thinking": think}
        if not think:
            extra_body["reasoning_effort"] = "none"
    model_settings: ModelSettings | None = (
        {"extra_body": extra_body} if extra_body else None
    )

    total_attempts = max(0, min(int(max_retries), 5)) + 1
    last_error: Exception | None = None
    last_invalid_text = ""
    refusal_count = 0
    attempt_seed = (options or {}).get("seed", 0) if isinstance(options, dict) else 0
    attempt_timeout = timeout_secs
    for attempt in range(1, total_attempts + 1):
        attempt_timeout = next_timeout_secs(timeout_secs, attempt)
        # Rebuilt each attempt so the escalated timeout actually takes
        # effect — httpx.AsyncClient's timeout is fixed at construction,
        # not mutable per-request.
        agent = _build_agent(
            base_url=base_url,
            model=model,
            schema=schema,
            headers=headers,
            timeout_secs=attempt_timeout,
        )
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
            seed = next_seed(options, attempt)
            attempt_seed = seed
            attempt_settings["seed"] = seed
            if "extra_body" in attempt_settings:
                # beacon-reviewer caught this: if a caller pinned options["seed"],
                # it's also sitting in extra_body.options.seed (the Ollama-native
                # passthrough). Left untouched, a backend that honors that nested
                # field over the top-level OpenAI "seed" above would keep sending
                # the same old seed on every retry — silently defeating this fix
                # for exactly the pinned-seed case. Copy rather than mutate in
                # place: extra_body/options here are the caller's own dicts,
                # shared across every attempt (and possibly other calls).
                # ModelSettings declares extra_body as `object` (it's an
                # opaque passthrough field), so a plain dict() call on it
                # doesn't type-check — cast first, this module always builds
                # it as a dict (see model_settings above).
                extra_body = dict(cast(dict, attempt_settings["extra_body"]))
                nested_options = dict(extra_body.get("options") or {})
                nested_options["seed"] = seed
                extra_body["options"] = nested_options
                attempt_settings["extra_body"] = extra_body
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
            output = cast(BaseModel, result.output)
            if refusal_cfg and refusal_cfg.get("enabled"):
                # Re-serialized, not the original wire text — pydantic-ai's
                # NativeOutput doesn't expose that separately, and the
                # regex/embedding check works the same either way (same
                # textual content, just re-encoded).
                content = output.model_dump_json()
                refused = await is_refusal(
                    content,
                    embed_fn=embed_fn,
                    embed_cache_key=refusal_cfg.get("embedding_model", ""),
                    threshold=refusal_cfg.get("threshold", 0.82),
                    custom_phrases=tuple(refusal_cfg.get("custom_phrases") or ()),
                )
                if refused:
                    refusal_count += 1
                    last_error = RuntimeError("refusal/deflection detected")
                    last_invalid_text = content
                    if attempt < total_attempts:
                        await asyncio.sleep(RETRY_BACKOFF_SECS)
                    continue
            record_attempt_info(
                attempt_info,
                seed=attempt_seed,
                attempts=attempt,
                timeout_secs=attempt_timeout,
                refusals=refusal_count,
            )
            return output
        except _STRUCTURED_OUTPUT_FAILURE_EXCEPTIONS as exc:
            last_error = exc
            last_invalid_text = str(exc)
            if attempt < total_attempts:
                await asyncio.sleep(RETRY_BACKOFF_SECS)

    record_attempt_info(
        attempt_info,
        seed=attempt_seed,
        attempts=total_attempts,
        timeout_secs=attempt_timeout,
        refusals=refusal_count,
    )
    raise RuntimeError(
        f"chat_structured: response failed validation against schema after "
        f"{total_attempts} attempt(s) (model={model!r}). Last error: "
        f"{last_error}. Last response (truncated): {last_invalid_text[:300]!r}"
    )
