# Phase 1 Data Model: VLM Image Input for ChatCompletion

**Spec**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

The feature adds **one optional field** to an existing model and defines how it
maps into each backend's wire shape. No new entities, no new socket types.

---

## Modified entity — `Message` (`src/comfydv/_llm/provider.py`)

```python
class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
    images: list[str] | None = None   # NEW — base64-encoded images (no data: prefix)
```

**Field: `images`**
- **Type**: `list[str] | None`, default `None`.
- **Meaning**: base64-encoded image payloads associated with this turn. `None`
  (or empty) means a text-only turn — **byte-for-byte identical to today**.
- **Carrier form**: raw base64 string, no `data:` URI prefix. Chosen because
  every target adapts *from* it (Ollama `images` array, OpenAI data-URI,
  pydantic-ai `BinaryContent`) — ADR-008.
- **Validation**: no format validation at the model layer (the model stays a
  dumb carrier); malformed data surfaces as a backend error (FR-006). A turn
  may carry ≥1 image; MVP exercises exactly one.
- **Serialization invariant**: provider payload construction MUST omit the
  `images` key when `None`/empty so existing text-only requests are unchanged
  (research.md Decision 2; FR-003, SC-004).

---

## Mapping table — one carrier, three wire shapes

| Path | Code site | Transform |
|---|---|---|
| Ollama free-text | `ollama_provider.py::chat` | none — `model_dump()`'s flat `images` array already matches `/api/chat`; only drop the key when empty |
| llama.cpp free-text | `llamacpp_provider.py::chat` | rebuild `content` as OpenAI parts: `[{"type":"text",...},{"type":"image_url","image_url":{"url":"data:image/png;base64,<b64>"}}]` |
| Structured (both) | `chat.py::chat_structured` | build `BinaryContent(data=b64decode(img), media_type="image/png")`; attach to `user_prompt` (last turn) / `UserPromptPart` (history turns) as `[text, *images]` |

---

## Node input — `ChatCompletion` (`src/comfydv/ollama.py`)

Add to `INPUT_TYPES["optional"]`:

```python
"image": ("IMAGE",),
```

- **Optional** — un-wired ⇒ `image=None` ⇒ the node builds exactly today's
  text-only user message. No new required input; no output/socket change
  (Constitution VI untouched — `RETURN_TYPES` positions 0/1 unchanged).
- When wired: encode the tensor to base64 PNG(s) (research.md Decision 4) and
  set them on the appended `Message(role="user", ...)`. History turns are not
  modified (FR-007).

### Encode helper (node-local, `comfy`/Pillow lazy)

```
_encode_image_tensor(image) -> list[str]:
    # image: ComfyUI IMAGE, torch float tensor [B, H, W, C] in 0..1
    # → for each frame: *255 → uint8 → PIL.Image.fromarray → PNG bytes → base64
    # returns [] for None/empty so callers treat it as "no image"
```

Lives in `ollama.py` (node module, already `comfy`-guarded). `src/comfydv/_llm/`
never imports torch/numpy/Pillow — it deals only in the base64 strings this
helper produces.

---

## State & relationships

- No persistent state; no new caching entity. Existing `_CHAT_RESPONSE_CACHE`
  keys already include the dumped messages, so an added `images` value
  participates in the cache key automatically (same image + prompt ⇒ cache
  hit), and a text-only turn's key is unchanged since the empty key is omitted.
- Relationship: `images` belongs to exactly one `Message` (one turn) — this is
  why the carrier is a message field, not a side-channel parameter (ADR-008
  Alternative A rejected).
