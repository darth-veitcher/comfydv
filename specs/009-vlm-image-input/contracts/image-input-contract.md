# Contract: Image Input across the LLMProvider boundary

**Spec**: [spec.md](../spec.md) · **Data model**: [data-model.md](../data-model.md) · **ADR**: [ADR-008](../../../project-management/ADRs/ADR-008-multimodal-image-input-across-llmprovider-boundary.md)

This feature adds no new protocol methods and no new socket types. The contract
below is the **behavioural conformance** every `LLMProvider` must satisfy for
the new `Message.images` field, plus the node's input contract.

---

## C1 — `Message.images` carrier

- `Message.images: list[str] | None = None`, base64 strings (no `data:` prefix).
- `images=None` or `[]` ⇒ the turn is text-only and MUST produce a request
  **byte-for-byte identical** to the pre-feature behaviour.

## C2 — `LLMProvider.chat()` conformance (both providers)

Given `messages` where the last user turn carries `images`:
1. The provider MUST transmit those images with that turn to its backend using
   its native shape (Ollama flat `images`; llama.cpp OpenAI `image_url` parts).
2. The provider MUST NOT transmit an `images` field for turns that have none
   (empty key omitted).
3. All existing behaviour is preserved: blank-retry-with-new-seed loop, response
   caching, timeout, and error surfacing are unchanged by the presence of images.
4. A backend that cannot process images (non-vision model / no `--mmproj`) MUST
   have its error surfaced to the caller, not swallowed (FR-006).

## C3 — `chat_structured()` conformance (shared helper, both providers)

1. Images on the last user turn MUST be attached as `BinaryContent` on the
   `Agent.run` `user_prompt`; images on history user turns MUST be attached to
   their `UserPromptPart`.
2. All existing structured guarantees hold unchanged: bounded retries (0–5),
   `RuntimeError` on exhaustion naming model/attempts/snippet, never returns a
   value that failed schema validation.
3. A text-only structured call MUST be indistinguishable from today's.

## C4 — `ChatCompletion` node input contract

1. Adds exactly one **optional** `image: ("IMAGE",)` input. No required input
   added; `RETURN_TYPES`/`RETURN_NAMES` positions unchanged (Constitution VI).
2. Un-wired ⇒ behaviour, request, and outputs identical to today.
3. Wired ⇒ image(s) attached to the current user turn only; `history` turns
   unchanged (FR-007).
4. Works with `structured_output=True` (C3) and free-text (C2) alike, on either
   backend, with no per-backend wiring difference (FR-004).

---

## Test contracts (test-first — Constitution III)

| ID | Level | Asserts |
|---|---|---|
| T1 | `Message` unit | `images` defaults `None`; round-trips base64 list; text-only dump omits the key |
| T2 | `OllamaProvider.chat` | image turn → payload message has flat `images:[...]`; text-only payload byte-identical to today (regression) |
| T3 | `LlamaCppProvider.chat` | image turn → `content` becomes text+`image_url` parts; text-only `content` stays a plain string (regression) |
| T4 | `chat_structured` | image turn builds `BinaryContent` on the prompt; text-only path unchanged; retry/validation contract intact |
| T5 | node encode helper | synthetic `[1,H,W,3]` tensor → decodable base64 PNG; `None`/empty → `[]` |
| T6 | node contract | optional `image` in `INPUT_TYPES`; un-wired run == today; wired run attaches to last turn only |

All tests run without a live ComfyUI or a live backend (mock at each provider's
own `_post_json`/`Agent.run` seam, per the `test_ollama_provider.py`
convention). T5 uses a synthetic tensor + Pillow (dev dep), no ComfyUI.
