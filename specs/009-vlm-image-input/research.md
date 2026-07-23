# Phase 0 Research: VLM Image Input for ChatCompletion

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **ADR**: [ADR-008](../../project-management/ADRs/ADR-008-multimodal-image-input-across-llmprovider-boundary.md)

ADR-008 recorded the boundary decision (images on `Message.images`, translated
per-provider) but deferred the exact wire shapes for live verification. This
file resolves them against the **installed** dependency versions and the
current provider code, not from memory.

---

## Decision 1 — pydantic-ai multimodal vehicle (structured-output path)

**Decision**: In the shared `chat_structured()` helper (`src/comfydv/_llm/chat.py`),
attach images as `pydantic_ai.messages.BinaryContent(data=<png bytes>,
media_type="image/png")` inside a `Sequence[UserContent]`. The current-turn
image rides on `Agent.run(user_prompt=[text, BinaryContent(...)])`; a
history turn's image rides on `UserPromptPart(content=[text, BinaryContent(...)])`.

**Rationale / verified**: Read directly from the pinned
`pydantic_ai_slim==2.9.0` source in this environment:

- `BinaryContent` (`messages.py:521`) — `__init__(self, data: bytes, *,
  media_type: ..., identifier=None, ...)`; exposes a `.base64` helper. `data`
  is **bytes**, so `chat.py` must `base64.b64decode()` the `Message.images`
  string into bytes when building it.
- `UserPromptPart.content: str | Sequence[UserContent]` (`messages.py:1022`)
  and `user_prompt` on `Agent.run` accept the same. `UserContent = str |
  TextContent | MultiModalContent | CachePoint` (`messages.py:899`), and
  `MultiModalContent` includes `BinaryContent`/`ImageUrl` — so a `[text,
  image]` list is the supported shape.
- `OpenAIChatModel` renders `BinaryContent` for images as an OpenAI
  `image_url` data-URI, and reads `BinaryContent.vendor_metadata['detail']`
  for the `detail` setting (documented in the field's own docstring).

**Consequence**: the structured path is provider-agnostic *for free* — both
Ollama and llama.cpp reach `/v1/chat/completions` through the same
`OpenAIChatModel`, so one change in `chat.py` covers structured output on both
backends. No per-provider structured code.

**Alternatives considered**: `ImageUrl(url="data:image/png;base64,...")` — also
supported, but requires assembling a data URI string; `BinaryContent` from raw
bytes + media type is the more direct representation of what we hold and lets
pydantic-ai own the data-URI formatting.

---

## Decision 2 — Ollama free-text path (`/api/chat`)

**Decision**: `OllamaProvider.chat()` sends each message's images as a flat
`images` array of **base64 strings** (no `data:` prefix) alongside `content`,
which is exactly Ollama's native `/api/chat` message schema. Because
`Message.images` already holds base64 strings, `Message.model_dump()` produces
the correct shape with **no transform** — the field flows straight through.

**Rationale / verified**: `OllamaProvider.chat()`
(`src/comfydv/_llm/ollama_provider.py:280`) already builds
`payload_messages = [m.model_dump() for m in messages]` and POSTs to
`/api/chat`. Ollama's documented `/api/chat` message object is
`{"role", "content", "images": [<base64>, ...]}` — the flat sibling field this
carrier maps onto directly. This is the reason base64 is the neutral carrier
form (ADR-008).

**Constraint discovered — byte-identical text path (FR-003/SC-004)**: adding
`images: list[str] | None = None` to `Message` means a text-only message would
dump as `{"role","content","images":null}`, changing today's request body.
Providers MUST drop a `None`/empty `images` before sending. Resolution:
serialize provider payload messages with the images key omitted when empty
(e.g. `model_dump(exclude_none=True)`, or drop the key explicitly). Guarded by
the existing Ollama provider tests, which assert the exact payload.

---

## Decision 3 — llama.cpp free-text path (`/v1/chat/completions`)

**Decision**: `LlamaCppProvider.chat()` maps a message carrying images into
OpenAI-style multimodal `content` **parts** before POSTing:
`content: [{"type":"text","text":<content>},
{"type":"image_url","image_url":{"url":"data:image/png;base64,<b64>"}}]`.
Messages with no images keep the plain-string `content` unchanged.

**Rationale / verified**: `LlamaCppProvider.chat()`
(`src/comfydv/_llm/llamacpp_provider.py:163`) builds
`payload_messages = [m.model_dump() for m in messages]` and POSTs to
`/v1/chat/completions`. Unlike Ollama, a flat `images` sibling is **not**
understood there — OpenAI's vision schema requires images inside `content` as
typed parts. `llama-server` implements this OpenAI-compatible multimodal
format **only when launched with a multimodal projector (`--mmproj`)**; without
it, image parts yield a server error (surfaced per FR-006, not crashed on).
This is the single point where the two providers genuinely diverge — exactly
the leakage ADR-008 localizes inside each provider.

**Alternatives considered**: normalizing Ollama *up* to content-parts too (one
shared mapper) — rejected in ADR-008 Alternative C: it forces the
currently-simpler Ollama path to do extra work and inverts "each provider owns
its wire format."

---

## Decision 4 — ComfyUI IMAGE tensor → base64 PNG (node layer)

**Decision**: The `ChatCompletion` node converts its optional `IMAGE` input to
base64 PNG(s) via Pillow: ComfyUI IMAGE is a float tensor `[B, H, W, C]` in
`0..1`; scale to `uint8`, `PIL.Image.fromarray(...)`, save PNG to an in-memory
buffer, base64-encode. A batch of `B` frames becomes `B` base64 strings in the
turn's `images` list (natural multi-image; MVP exercises `B=1`). The import of
Pillow/numpy is **lazy** (inside the encode function), so the module still
imports cleanly outside ComfyUI (Constitution IV).

**Rationale**: Pillow is the ComfyUI-ecosystem standard for IMAGE tensor ↔
file and is present in every ComfyUI install; numpy comes with torch. Neither
is added to comfydv's **core** runtime deps — they are ComfyUI-provided, the
same stance the repo already takes for torch (dev-only in `pyproject.toml`).
To keep the encoder **test-first** (Constitution III) without a live ComfyUI,
add `pillow` to the **dev** dependency group so a unit test can feed a
synthetic `numpy`/`torch` tensor through the pure encode function and assert a
decodable PNG.

**Boundary kept clean**: only the node (`src/comfydv/ollama.py`, already
`comfy`-guarded) touches tensors/Pillow. Everything in `src/comfydv/_llm/`
deals purely in base64 strings and stays unit-testable with hand-crafted
strings — no torch, numpy, or Pillow import there.

**Edge cases (FR-006, Edge Cases)**: an un-wired optional input arrives as
`None` → node builds today's exact text-only message. A zero-size / empty batch
tensor → treated as "no image". A non-vision model or non-`mmproj` server
returns a backend error → surfaced with a clear message, never a silent
image-less answer.

---

## Decision 5 — where the image attaches on the turn (FR-007)

**Decision**: The node attaches images to the **current user turn only** — the
`Message(role="user", content=prompt, images=[...])` it already appends. Prior
`history` turns are untouched. The structured helper likewise only lifts images
onto the final user turn (and any history turn that already carried them),
matching its existing "last message is the prompt" contract
(`chat.py:106`, which requires `messages[-1].role == "user"`).

---

## Summary of resolved unknowns

| Unknown (from ADR-008) | Resolved to |
|---|---|
| pydantic-ai multimodal type | `BinaryContent(data=bytes, media_type="image/png")` — verified in installed 2.9.0 |
| Structured path per-provider? | No — shared via `OpenAIChatModel`; one change in `chat.py` |
| Ollama wire shape | flat `images: [base64]` on the message; passes through `model_dump()` |
| llama.cpp wire shape | OpenAI `image_url` content-parts; requires `--mmproj` |
| Text-path byte-identity | drop empty `images` key in provider payloads (guarded by existing tests) |
| Tensor → base64 | Pillow, lazy import in node; `pillow` added to dev deps for testability |
| No new runtime deps | Confirmed — Pillow/numpy are ComfyUI-provided, dev-only here |

No `NEEDS CLARIFICATION` remain.
