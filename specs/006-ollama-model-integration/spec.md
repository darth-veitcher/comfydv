# Feature Specification: Ollama Model Integration

**Feature Branch**: `006-ollama-model-integration`

**Created**: 2026-06-28

**Status**: Draft

**Epic**: `ollama-integration`

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Configure Ollama Connection (Priority: P1)

A ComfyUI user wants to connect their workflows to a locally-running Ollama server. They add an **Ollama Client** node, type in the server address (or leave the default for localhost), and wire its output to every downstream Ollama node. The address is set once; changing it propagates immediately to all connected nodes.

**Why this priority**: Without a working connection, no other Ollama node can function. This is the foundational building block.

**Independent Test**: Add an Ollama Client node, set the host to a running Ollama server, and confirm that connecting its output to a model selector node causes the model list to populate correctly.

**Acceptance Scenarios**:

1. **Given** Ollama is running at `http://localhost:11434`, **When** the user adds an Ollama Client node and leaves the host at its default value, **Then** the node outputs a valid connection handle that downstream nodes can use.
2. **Given** an Ollama Client node is wired to a model selector, **When** the user changes the host field on the client node, **Then** the selector refreshes its model list from the new host.
3. **Given** an unreachable host is entered, **When** a downstream node tries to use the connection, **Then** ComfyUI surfaces a clear error message naming the unreachable host — no hang, no crash.

---

### User Story 2 — Browse and Select Available Models (Priority: P1)

A ComfyUI user wants to pick which Ollama model to use without memorising model names. They add an **Ollama Model Selector** node and see a live dropdown showing every model installed on their Ollama server. They choose one; the node outputs the model's name string for wiring to other nodes.

**Why this priority**: Correct model selection is required before load or inference; a live dropdown eliminates the primary source of user error (Issue #1 root cause).

**Independent Test**: Add a Model Selector node wired to a running Ollama Client; confirm the dropdown lists all installed models and outputs the selected name as a string.

**Acceptance Scenarios**:

1. **Given** Ollama has two or more models installed, **When** the user adds a Model Selector node connected to a working client, **Then** the dropdown lists all installed models by name.
2. **Given** no models are installed, **When** the Model Selector renders, **Then** the dropdown is empty and the node displays a warning rather than an error.
3. **Given** a model is selected in the dropdown, **When** the node runs, **Then** the output is the exact model name string (matching what Ollama's `/api/tags` returns).

---

### User Story 3 — Load and Unload Models (Priority: P2)

A ComfyUI user wants to pre-load a model into Ollama's memory before running inference (to reduce first-response latency) and unload it afterwards to free resources. They add **Ollama Load Model** and **Ollama Unload Model** nodes, each with a live model dropdown (same as the selector), and wire them into their workflow.

**Why this priority**: Fixes Issue #1 — these two nodes currently lack a model dropdown, forcing users to type model names and causing empty-model validation failures. Unload is the natural complement.

**Independent Test**: Wire a Load Model node to a running client and confirm the dropdown lists models; run the node and confirm Ollama reports the model as loaded.

**Acceptance Scenarios**:

1. **Given** a Load Model node connected to a working client, **When** the node is placed on the canvas, **Then** the model field displays a live dropdown populated from the connected Ollama server (not a blank text box). *(Fixes Issue #1)*
2. **Given** a model is selected in the Load Model dropdown and the node runs, **When** the run completes, **Then** the model is loaded into Ollama memory and the node outputs the loaded model name.
3. **Given** an Unload Model node wired to a client and a model name, **When** the node runs, **Then** Ollama evicts the model from memory.
4. **Given** the Load Model or Unload Model node is run with an empty model name, **When** the run executes, **Then** the node raises a validation error before contacting Ollama — it never sends an empty model name.

---

### User Story 4 — Generate Text via Chat Completion (Priority: P2)

A ComfyUI user wants to send a prompt to a locally-running Ollama model and receive the response text as a string they can wire to other nodes. They add an **Ollama Chat Completion** node, pick a model from its live dropdown, wire in a prompt, and run. The node returns the model's response and an updated conversation history for multi-turn use.

**Why this priority**: This is the primary inference node — the reason the whole feature exists.

**Independent Test**: Wire a Chat Completion node to a running client, select a model from the dropdown, enter a fixed prompt, run the workflow, and confirm the response text is non-empty and plausible.

**Acceptance Scenarios**:

1. **Given** a Chat Completion node with a working client, **When** it is placed on the canvas, **Then** the model field shows a live dropdown (not a text box). *(Fixes Issue #1)*
2. **Given** a prompt `"Say hello"` is wired in and a model is selected, **When** the node runs, **Then** the output `response` is a non-empty string containing a greeting.
3. **Given** a previous history list is wired into the `history` input, **When** the node runs, **Then** the model receives the full conversation context and the output history includes the new turn appended.
4. **Given** generation options (e.g. temperature = 0.1) are wired in via the options socket, **When** the node runs, **Then** those options are forwarded to the Ollama API — the response is deterministic at temperature 0 with a fixed seed.

---

### User Story 5 — Tune Inference with Composable Option Nodes (Priority: P3)

A ComfyUI user wants to control how Ollama generates text (temperature, seed, token limits, etc.) without crowding the Chat Completion node with a wall of widgets. They chain one or more **Option** nodes (each setting one parameter) and wire the combined output to the Chat Completion node.

**Why this priority**: Composable options provide UX clarity for power users; each option node is a focused single-responsibility node.

**Independent Test**: Wire a Temperature option node (value = 0.0) and a Seed option node (value = 42) into a Chat Completion node; run twice and confirm identical outputs.

**Acceptance Scenarios**:

1. **Given** a Temperature option node set to `0.0` is wired to a Chat Completion node, **When** the workflow runs twice with the same prompt, **Then** the response text is identical both times.
2. **Given** two option nodes are chained (Temperature → Seed), **When** wired to Chat Completion, **Then** both parameters reach the Ollama API (verified by observing deterministic outputs).
3. **Given** no option nodes are connected, **When** Chat Completion runs, **Then** Ollama uses its server-side defaults — no error from a missing options input.

---

### User Story 6 — Inspect Conversation History (Priority: P3)

A ComfyUI user building a multi-turn conversation workflow wants to debug the history accumulating across turns or use its length to branch their workflow conditionally. They add **Ollama Debug History** (to inspect) or **Ollama History Length** (to count turns) nodes.

**Why this priority**: Utility nodes for power users building complex multi-turn workflows; low risk but high usefulness for debugging.

**Independent Test**: Build a two-turn conversation, wire the history output to a Debug History node, run, and confirm the output string shows both turns. Wire to History Length and confirm output is `2`.

**Acceptance Scenarios**:

1. **Given** a history list from a Chat Completion node (two turns), **When** wired to Debug History, **Then** the output is a human-readable string showing both turns.
2. **Given** a history list with three turns, **When** wired to History Length, **Then** the integer output is `3`.
3. **Given** an empty history (no prior turns), **When** wired to either utility node, **Then** Debug History returns an empty string (or `"[]"`), History Length returns `0`.

---

### Edge Cases

- **Ollama unreachable**: All nodes that communicate with Ollama must raise a descriptive, ComfyUI-visible error (not hang or crash the server process).
- **Empty model dropdown**: When no models are installed, nodes with model dropdowns render with an empty dropdown and show a warning — they do not throw an unhandled error at canvas render time.
- **Very long responses**: No streaming; full response is returned as a string. Truncation is the user's responsibility (e.g. via a downstream node).
- **Concurrent workflow runs**: Ollama handles concurrency server-side; these nodes make one request per node execution and do not manage request queuing.
- **Model name not found**: Ollama returns an error; the node surfaces it as a ComfyUI-visible error with the model name included.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a connection configuration node that accepts a server address and outputs a typed connection handle; all other Ollama nodes MUST accept this handle as input rather than embedding the server address themselves.
- **FR-002**: The Model Selector node MUST fetch the list of installed models from the connected Ollama server at node placement and display them as a selectable dropdown.
- **FR-003**: The Load Model node MUST display a live model dropdown (not a plain text input), eliminating the need to type model names. *(Fixes Issue #1)*
- **FR-004**: The Chat Completion node MUST display a live model dropdown (not a plain text input). *(Fixes Issue #1)*
- **FR-005**: The Chat Completion node MUST accept: a connection handle, a model name (from dropdown), a prompt string, an optional generation-options bundle, and an optional conversation history list. It MUST output the response text and the updated history list.
- **FR-006**: The Load Model node MUST send a load request to Ollama for the selected model and output the loaded model name.
- **FR-007**: The Unload Model node MUST send an unload request to Ollama for the named model.
- **FR-008**: The system MUST provide seven composable option nodes, each setting exactly one inference parameter (temperature, seed, max tokens, top-p, top-k, repeat penalty, extra body). Each MUST accept an optional upstream options bundle and output an extended bundle.
- **FR-009**: The Debug History node MUST accept a history list and return a human-readable string.
- **FR-010**: The History Length node MUST accept a history list and return its length as an integer.
- **FR-011**: All 14 nodes MUST be registered under the `dv/` category in ComfyUI.
- **FR-012**: All nodes MUST use the project's standard logging mechanism — no third-party logging libraries. (ADR-001, ADR-002)
- **FR-013**: All Ollama HTTP communication MUST use a HTTP library already present in the ComfyUI dependency tree — no new HTTP dependencies are added to the project. (ADR-003, ADR-004)
- **FR-014**: The web widget extension for live model dropdowns MUST be merged into the project's existing JavaScript extension file structure.
- **FR-015**: When the Ollama server is unreachable or returns an error, every affected node MUST surface a descriptive error message in ComfyUI — it MUST NOT hang or crash the ComfyUI server process.

### Key Entities

- **Ollama Connection** (`OLLAMA_CLIENT`): A typed handle carrying the Ollama server URL. Produced by the client node; consumed by all other Ollama nodes.
- **Model Name**: A plain string identifying an Ollama model (e.g. `"llama3.2:latest"`). Populated via live dropdown on selector, load model, and chat completion nodes.
- **Conversation History** (`OLLAMA_HISTORY`): An ordered list of message turns, each with a role (`user`/`assistant`) and content string. Accumulated across multiple Chat Completion node executions.
- **Generation Options** (`OLLAMA_OPTIONS`): An accumulating bundle of inference parameters (temperature, seed, etc.). Built by chaining option nodes; consumed by Chat Completion.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can wire an Ollama Client node once and connect it to any number of downstream Ollama nodes without re-entering the server address. All connected nodes use the same address.
- **SC-002**: The model dropdown on Model Selector, Load Model, and Chat Completion nodes is populated automatically from the connected Ollama server — users never type a model name by hand.
- **SC-003**: A complete end-to-end workflow (client → model selector → load model → chat completion with at least one option node → response string output) assembles and executes without manual configuration beyond the server address.
- **SC-004**: When the Ollama server is unreachable, every node that requires it surfaces a named error in ComfyUI within 5 seconds — no node hangs or crashes the ComfyUI server process.
- **SC-005**: All 14 new nodes appear under the `dv/` category and coexist with existing comfydv nodes without name collisions or import errors.
- **SC-006**: The project's CI smoke test passes with all 14 new nodes registered, with no new failing tests in the existing test suite.
- **SC-007**: Issue #1 on `darth-veitcher/comfyui-ollama-model-manager` is confirmed resolved: an empty-model validation error can no longer be triggered by normal node placement.

---

## Assumptions

- Ollama is installed separately by the user; these nodes do not install, configure, or start the Ollama server.
- The user has at least one model available in their Ollama installation to use inference nodes (selector/load/chat); the connection node works regardless.
- Conversation history is managed within the workflow and is not persisted between ComfyUI sessions.
- All nodes target single-user local use; multi-user concurrency and authentication are out of scope (ADR-005).
- GPU/CPU selection for inference is controlled by Ollama server configuration, not by these nodes.
- The existing `dv/` ComfyUI category (used by Format String, Random Choice, Circuit Breaker) is the correct category for the new nodes; no new category is required.
- The HTTP library already in the ComfyUI dependency tree is `aiohttp`; all async Ollama HTTP calls use it (ADR-004).
- `loguru` and `rich` (used in the source repo) are replaced by stdlib `logging` with the NullHandler pattern established in ADR-001 and ADR-002.
- Post-ship archival of `darth-veitcher/comfyui-ollama-model-manager` and closure of Issue #1 with a redirect comment are SHIP-phase tasks, not implementation tasks, and are not tracked in this spec's tasks.md.
