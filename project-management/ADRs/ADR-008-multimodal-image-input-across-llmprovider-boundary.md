# ADR-008: Multimodal image input carried on the Message across the LLMProvider boundary

## Status

> Proposed

_Date:_ 2026-07-22
_Deciders:_ darth-veitcher

---

## Context

The `ChatCompletion` node and the `LLMProvider` protocol (ADR-007) are
text-only today. `Message` (`src/comfydv/_llm/provider.py`) carries a single
`content: str`; `ChatCompletion`'s `INPUT_TYPES` (`src/comfydv/ollama.py`)
exposes no `IMAGE` socket. Users want to couple the existing chat node with a
vision-capable model (a VLM) to describe or reason about an image produced
elsewhere in a ComfyUI workflow.

ADR-007 deliberately scoped this out: it defined `Message` as text-only and
recorded that "if llama.cpp's router mode needs a protocol capability that
doesn't exist yet, that is a protocol change scoped as its own follow-up, not
silently special-cased." This ADR is that follow-up — it extends the same
adapter pattern to a second input modality.

The two shipped backends carry images very differently on the wire, and the
node has two distinct code paths (free-text vs structured), so a decision is
needed about **where** an image lives as it crosses the provider boundary and
**who** translates it into each backend's native shape:

- **Ollama free-text** — `OllamaProvider.chat()` posts `[m.model_dump() for m
  in messages]` to the native `/api/chat`, which accepts a per-message
  `images` field: an array of base64-encoded image data alongside the text
  `content`.
- **llama.cpp free-text** — `LlamaCppProvider.chat()` posts to the
  OpenAI-compatible `/v1/chat/completions`, where a message's `content` is a
  list of typed parts (`{"type": "text", ...}`,
  `{"type": "image_url", "image_url": {"url": "data:image/...;base64,..."}}`)
  — a flat sibling `images` field is not understood.
- **Structured output (both backends)** — routed through the shared
  `chat_structured()` helper (`src/comfydv/_llm/chat.py`) over pydantic-ai,
  which represents images as typed multimodal content
  (`BinaryContent` / `ImageUrl`) inside the user prompt, not as a raw request
  field.

The competing concern is DRY vs. leakage: a single carrier keeps the graph and
the node backend-agnostic (ADR-007's whole point), but the per-backend wire
shapes are irreducibly different and must be translated somewhere.

## Decision

**Carry images as an optional field on `Message`, and make each provider
responsible for translating that field into its own native wire shape** — the
exact same division of responsibility ADR-007 established for text and model
management (operation-level protocol, wire-format quirks contained inside each
provider).

1. **Protocol** — extend `Message` with an optional
   `images: list[str] | None = None`, where each entry is a base64-encoded
   image. `content` stays required; a text-only message sets `images=None` and
   is byte-for-byte unchanged from today (`model_dump()` omits it or emits
   `null`), so all existing Ollama/llama.cpp behavior is preserved.

2. **Node** — `ChatCompletion` gains one **optional** `image: ("IMAGE",)`
   input. When wired, the node encodes the ComfyUI `IMAGE` tensor to base64
   and attaches it to the user `Message` it already constructs. When not
   wired, the node builds exactly the message it builds today. The node never
   branches on which concrete provider it holds — consistent with ADR-007.

3. **Per-provider translation** (the leakage lives here, deliberately):
   - `OllamaProvider.chat()` — the flat `images` field on the dumped message
     already matches Ollama's native `/api/chat` schema; it flows through with
     no transform.
   - `LlamaCppProvider.chat()` — maps a message's `images` into OpenAI-style
     `image_url` content parts before POSTing to `/v1/chat/completions`.
   - `chat_structured()` (shared) — maps the last user message's `images` into
     pydantic-ai multimodal content on the `user_prompt`; both backends inherit
     this single implementation, mirroring how they already share the
     structured text path.

4. **No new node classes and no new socket types** — image support is an
   additional optional input on the *existing* generic node, so a workflow
   author gains vision by wiring one socket, not by learning a new node. This
   is the direct extension of ADR-007's "generic, not per-backend" node stance.

The base64 string is the neutral interchange form at the boundary because it
is the one representation every target consumes (Ollama's `images` array,
OpenAI's `data:` URI, and pydantic-ai's `BinaryContent` all accept it),
keeping the `Message` carrier itself provider-agnostic.

_Wire specifics (exact Ollama `/api/chat` image field, llama.cpp multimodal
readiness via `mmproj`, and pydantic-ai's multimodal content type) are
verified live in this feature's `research.md`/`plan.md` per project
convention, not assumed from training data._

## Consequences

**Easier:**
- One carrier (`Message.images`) and one node change unlock vision on both
  backends at once; a future third provider implements image translation in
  its own `chat()` exactly as it implements text, with no protocol churn.
- The graph and the node stay backend-agnostic — swapping providers still
  means rewiring one client node, now including the image path.
- Text-only workflows are entirely unaffected (additive optional field +
  optional socket).

**Harder / constrained:**
- `Message` is no longer a trivially-uniform text struct; each provider's
  `chat()` (and the shared structured helper) must handle the `images` field,
  even if only to pass it through. This is accepted leakage, localized to the
  provider layer — the same tradeoff ADR-007 already made for `keep_alive` vs
  explicit load/unload.
- Vision requires a model actually loaded with multimodal weights (Ollama
  multimodal models; llama.cpp launched with an `mmproj` projector). A
  text-only model receiving images degrades to a backend error, not a node
  crash — surfacing that clearly is a spec requirement, not something this
  boundary can prevent.

**Debt introduced:**
- None deliberately, contingent on text-only requests remaining byte-identical
  to today (guarded by the existing Ollama/llama.cpp provider tests, which must
  stay green).

## Considered Alternatives

### Alternative A: A separate `images` parameter threaded through `chat()`/`chat_structured()` signatures

**Why rejected:** Widens every provider method signature and the protocol for
a value that is conceptually part of a message turn. Images belong to a
specific message (which turn the picture accompanies), and multi-turn vision
histories need per-message association — a single side-channel parameter can't
express that. Putting it on `Message` keeps turn/image association intact and
leaves method signatures unchanged.

### Alternative B: A dedicated multimodal node / socket type separate from `ChatCompletion`

**Why rejected:** Reintroduces exactly the per-capability node proliferation
ADR-007 eliminated. A workflow author would maintain two chat nodes and
relearn one for vision. An optional input on the existing node is strictly
simpler and keeps the "one generic node set" promise.

### Alternative C: Normalize images to OpenAI content-parts at the boundary; make Ollama un-translate

**Why rejected:** Picks OpenAI's shape as the canonical form and forces the
Ollama provider — whose native API wants the simpler flat `images` array — to
convert *away* from it. That inverts the "each provider owns its own wire
format" principle and does more work on the currently-simpler path. A neutral
base64 carrier that every backend adapts *from* is the orthogonal choice.

---

## Links

- Related epic: `project-management/Roadmap/epics/vlm-image-input.md`
- Related spec: `specs/009-vlm-image-input/`
- Related ADRs: [ADR-007](ADR-007-llm-provider-adapter-pattern.md) (extended — same adapter pattern, second input modality), [ADR-005](ADR-005-ollama-host-config-via-client-node.md) (client-node pattern, unchanged)
- External reference: GitHub issue #15 (llama.cpp parity), Ollama multimodal `/api/chat` `images`, OpenAI vision `image_url` content parts
