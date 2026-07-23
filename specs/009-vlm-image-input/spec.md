# Feature Specification: VLM Image Input for ChatCompletion

**Feature Branch**: `009-vlm-image-input`

**Created**: 2026-07-22

**Status**: Draft

**Input**: User description: "Let a workflow author wire a ComfyUI IMAGE into the existing generic ChatCompletion node so a vision-capable model (VLM) on either backend (Ollama multimodal models, llama.cpp multimodal via mmproj) can describe or understand the image. Provider-agnostic per ADR-007/ADR-008: the node attaches the image to the user message; each provider maps it to its own wire format. The Message carrier gains an optional image field; text-only behaviour is unchanged when no image is wired."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Describe an image with a chat node (Priority: P1) 🎯 MVP

As a ComfyUI workflow author with a vision-capable model available, I want to
wire an image into the chat node I already use and get back a text description
or answer about that image, so I can add image understanding to a workflow
without learning a new node.

**Why this priority**: This is the entire point of the feature — a picture in,
a text understanding out — and the proof that image input works through the
existing generic node on at least one backend.

**Independent Test**: Wire any image source into the chat node's image input,
point the node at a loaded vision-capable model, run the workflow, and confirm
the response text describes the wired image.

**Acceptance Scenarios**:

1. **Given** a chat node connected to a backend with a vision-capable model loaded and an image wired into the node's image input, **When** the workflow executes with a prompt like "describe this image", **Then** the node returns a text response that reflects the actual content of the wired image.
2. **Given** the same chat node with **no** image wired, **When** the workflow executes, **Then** the node behaves exactly as it does today — text-only chat, identical response for identical text input — with no new required inputs and no change in output.

---

### User Story 2 - Same image input on either backend (Priority: P1)

As a workflow author, I want image input to work the same way whether my chat
node is connected to Ollama or to llama.cpp, so I don't have to rebuild or
relearn the image path when I switch backends — exactly as text and structured
output already behave identically across the two.

**Why this priority**: The generic-node promise (ADR-007) is the reason this
feature is small; this story is what proves the image path honours it rather
than quietly becoming backend-specific.

**Independent Test**: Run User Story 1 unchanged against an Ollama connection
and against a llama.cpp connection (each with a vision-capable model), and
confirm both return a description of the wired image using the identical node
setup.

**Acceptance Scenarios**:

1. **Given** a workflow that describes an image via the chat node wired to Ollama, **When** the connection node is swapped to a llama.cpp one (pointed at a server with a multimodal model) with no other change, **Then** the workflow still returns a description of the same image.
2. **Given** equivalent image + prompt inputs on both backends, **When** each workflow executes, **Then** both produce a coherent image-grounded text response — no backend requires a different node, input shape, or wiring for the image.

---

### User Story 3 - Structured output about an image (Priority: P2)

As a workflow author, I want to combine image input with the node's existing
structured-output mode, so a VLM can return schema-validated fields extracted
from an image (for example a caption, a list of detected objects, or a
yes/no), not just free text.

**Why this priority**: Structured output is an existing, valued capability;
making it work with images turns "describe this" into usable, wired,
downstream-typed data. It builds on User Story 1 and is lower risk to defer
than getting basic image chat working at all.

**Independent Test**: Enable structured output on the chat node with a schema,
wire an image, run against a vision-capable model, and confirm each schema
field is populated from the image and no required field is blank.

**Acceptance Scenarios**:

1. **Given** the chat node with an image wired and structured output enabled with a valid schema, **When** the workflow executes against a vision-capable model, **Then** each schema field is available as its own typed output, populated from the image, with no required field blank.
2. **Given** the same setup where the model first returns invalid or incomplete structured output, **When** the workflow executes, **Then** the node retries and, if still unsuccessful, fails with a clear error — the same retry/validation behaviour the text-only structured path already guarantees.

---

### Edge Cases

- What happens when an image is wired but the selected model is **not**
  vision-capable? The node must surface a clear error attributable to the model
  lacking image support, not crash and not silently drop the image and answer
  as if none was sent.
- What happens when the backend server is reachable but was not started with
  multimodal support (e.g. a llama.cpp server launched without an `mmproj`
  projector)? The node should report a clear, specific error rather than an
  unhelpful generic failure.
- What happens with an empty or zero-size image input, or an image input that
  is wired but carries no actual image data? The node should treat it as "no
  image" or report a clear error — never send a malformed request.
- What happens when both an image and a multi-turn history are present? The
  image must be associated with the current user turn, and prior turns must
  remain unaffected.
- What happens to the node's text-only path for a model/backend that does not
  understand images at all — does an un-wired image input leave the request
  byte-for-byte identical to today's? (It must.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST let a workflow author provide an image to the existing chat node through a single, **optional** image input — no new node and no new required input.
- **FR-002**: When an image is provided, the system MUST include it with the current user turn sent to the connected model, so a vision-capable model can ground its response in that image.
- **FR-003**: When **no** image is provided, the system MUST send exactly the request it sends today — text-only behaviour, inputs, and outputs unchanged, with no regression for existing workflows.
- **FR-004**: Image input MUST work identically across both supported backends from the workflow author's perspective — same node, same wiring, same input shape — with each backend's differing native image format handled internally, not exposed on the graph.
- **FR-005**: Image input MUST be compatible with the node's existing structured-output mode: an image-grounded response can be schema-validated with the same retry and validation guarantees as the text-only structured path.
- **FR-006**: The system MUST surface a clear, specific error when an image is provided but the target model or backend cannot process images (non-vision model, or a server without multimodal support), rather than crashing or silently discarding the image.
- **FR-007**: The system MUST associate a provided image with the current user turn only, leaving any prior conversation history unchanged.

### Key Entities *(include if feature involves data)*

- **Chat message**: The existing per-turn unit of a chat request. Extended so a
  turn can optionally carry one or more images in addition to its text; a
  turn with no image is unchanged from today.
- **Image input**: An image supplied on the workflow canvas (the standard
  ComfyUI image type) and attached to the current user turn; provider-neutral
  at the boundary, translated to each backend's native shape internally.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A workflow author can make an existing chat node describe a wired image by adding exactly one connection (the image), with no new node and no other node changes.
- **SC-002**: The same image-describing workflow runs unchanged when repointed from one backend to the other — zero edits beyond swapping the connection node.
- **SC-003**: Structured-output workflows with an image populate every required schema field from the image content, with zero blank-required-field results, matching the text-only structured guarantee.
- **SC-004**: Every existing text-only workflow produces identical results after this feature ships — no observable change when no image is wired (existing backend behaviour tests remain green).
- **SC-005**: Providing an image to a non-vision model or a non-multimodal server yields a clear, specific error in 100% of such cases — never a crash and never a silently image-less answer presented as if the image was seen.

## Assumptions

- Workflow authors run their own backend (Ollama or llama.cpp) with a
  vision-capable model available and loaded; for llama.cpp this means the
  server was launched with a multimodal projector (`mmproj`). This feature does
  not install, configure, download, or launch vision models.
- Scope is still **images only** — no video, audio, or document modalities; and
  image **input** only — no image generation or output.
- A single image per turn is the primary target; carrying more than one image
  per turn is a natural extension of the same carrier but is not a required
  acceptance criterion of the MVP.
- The generic `ChatCompletion` node, the `LLMProvider` protocol, and both
  providers already exist (ADR-007) and are extended, not replaced; the
  cross-provider image-carrier decision is recorded in ADR-008.
- The standard ComfyUI image type is the input; converting it to the neutral
  form each backend consumes is an internal concern of this feature, not
  something the workflow author sees.
