# Feature Specification: llama.cpp Model Integration

**Feature Branch**: `008-llamacpp-integration`

**Created**: 2026-07-11

**Status**: Draft

**Input**: User description: "Add ComfyUI nodes for llama.cpp local inference via llama-server's router mode, implementing the LlamaCppProvider as the second LLMProvider (ADR-007) alongside the existing OllamaProvider. Router mode exposes GET /models (with live status), POST /models/load, POST /models/unload, giving llama.cpp the same manual load/unload memory-management primitives as Ollama. No new ComfyUI node classes needed for chat/model-selection/load/unload — only a new LlamaCppClient config node; the existing generic ChatCompletion/LLMModelSelector/LLMLoadModel/LLMUnloadModel nodes work unchanged once wired to it."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect to a local llama.cpp server and get chat responses (Priority: P1) 🎯 MVP

As a ComfyUI workflow author running `llama-server` locally, I want a connection node for it — just like the one I already use for Ollama — so I can get chat responses from a llama.cpp-hosted model using the same chat node I already know.

**Why this priority**: This is the entire point of the feature and the proof that the provider abstraction (shipped in the prerequisite epic) actually works: a second backend, zero changes to the chat node.

**Independent Test**: Wire a new llama.cpp connection node into the existing chat node, run against a local `llama-server` (router mode), confirm a text response.

**Acceptance Scenarios**:

1. **Given** a running local `llama-server` (router mode) and a workflow with a llama.cpp connection node wired into the existing chat node, **When** the workflow executes, **Then** the chat node returns the model's text response — using the exact same chat node a workflow author already uses for Ollama.
2. **Given** the llama.cpp connection node configured with an unreachable server address, **When** the workflow executes, **Then** the chat node reports a clear connection error, matching the behavior workflow authors already know from the Ollama connection.

---

### User Story 2 - Get structured, validated output from llama.cpp (Priority: P1)

As a workflow author, I want structured output (a schema-validated response instead of free text) to work identically regardless of whether I'm connected to Ollama or llama.cpp, so I don't have to relearn or rebuild anything when switching backends.

**Why this priority**: Structured output is a core existing capability (already proven for Ollama); this story proves the shared mechanism genuinely generalizes rather than being Ollama-specific in practice, not just in name.

**Independent Test**: Enable structured output on the chat node with a schema, run against a llama.cpp-hosted model, confirm each schema field is populated and never blank — using the same steps as the equivalent Ollama test.

**Acceptance Scenarios**:

1. **Given** a chat node connected to llama.cpp with structured output enabled and a valid schema, **When** the workflow executes and the model responds correctly, **Then** each schema field is available as its own typed output, and no required field is blank.
2. **Given** a llama.cpp-hosted model that returns invalid or incomplete structured output, **When** the workflow executes, **Then** the node retries automatically and, if still unsuccessful, fails with a clear error — identical behavior to the Ollama path.

---

### User Story 3 - See and control which models are loaded on llama.cpp (Priority: P2)

As a workflow author running models locally, I want to see live model status (including whether a model is currently loading or being downloaded, not just loaded/unloaded) and explicitly load or unload a model on my llama.cpp server, so I can manage memory the same way I already do for Ollama — with more visibility, since llama.cpp's router mode reports richer status than Ollama does.

**Why this priority**: Valuable and proves the model-management path generalizes too, but a workflow can still run chat completions without ever calling load/unload explicitly (the server can load on first use), so it's lower risk to defer than basic chat.

**Independent Test**: Use the existing model-listing node against a running `llama-server`, confirm it shows each available model with its current status (including `loading`/`downloading` if applicable); use the existing load/unload nodes against one model and confirm its status changes.

**Acceptance Scenarios**:

1. **Given** a running local `llama-server` with at least one available model, **When** a workflow author uses the model-listing node, **Then** they see each available model along with its current status, drawn from llama.cpp's full status vocabulary (not just loaded/unloaded).
2. **Given** a model that is not currently loaded, **When** a workflow author runs the load-model node against it, **Then** the model becomes loaded and is then usable by the chat node.
3. **Given** a model that is loaded and idle, **When** a workflow author runs the unload-model node against it, **Then** the model is freed from memory and its reported status updates accordingly.

---

### User Story 4 - Swap from Ollama to llama.cpp without touching the rest of the workflow (Priority: P3)

As a workflow author with an existing Ollama-based workflow, I want to switch it to llama.cpp by changing only the connection node, so I don't have to rebuild my chat/model-management logic for a second backend.

**Why this priority**: This is the adapter pattern's actual promise made concrete for a user, but it's a validation/demonstration story rather than new capability — everything it depends on is already covered by User Stories 1–3.

**Independent Test**: Take a workflow using the Ollama connection node, replace it with the llama.cpp connection node (same downstream nodes, no other changes), run it, confirm it still works.

**Acceptance Scenarios**:

1. **Given** a workflow with chat/model-management nodes wired to an Ollama connection node, **When** a workflow author replaces only the connection node with a llama.cpp one (pointed at a running `llama-server`), **Then** the workflow runs successfully with no changes to any other node.

---

### Edge Cases

- What happens when `llama-server` is running but was launched without router mode (i.e. with `-m` instead of `--models-dir`)? The router-mode-only endpoints this feature depends on won't exist — the connection/model-management nodes should fail with a clear error, not hang or silently return empty results.
- What happens when the configured server address is unreachable at the moment a model-listing, load, or unload node runs (not just the chat node)?
- What happens when llama.cpp reports a model status this feature doesn't expect (a router-mode API change)? Should degrade gracefully (surface the status if recognized, don't crash on an unrecognized one), not silently misreport.
- What happens to an in-flight chat request if the model it depends on is unloaded by another node in the same workflow run? (Same question already answered for Ollama — behavior should be consistent.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow a workflow author to configure a connection to a local `llama-server` (router mode) the same way they already configure a connection to Ollama — a dedicated connection node, reusable across multiple nodes in a workflow.
- **FR-002**: The system MUST NOT require any new or different node classes for chat, structured output, model listing, or load/unload when using llama.cpp — the existing generic nodes MUST work unchanged once connected to a llama.cpp connection node.
- **FR-003**: The system MUST report each model's status using llama.cpp's full status vocabulary (unloaded, loading, loaded, sleeping, downloading) when connected to llama.cpp — not degraded to the narrower Ollama-compatible set.
- **FR-004**: The system's chat and structured-output behavior MUST be identical between Ollama and llama.cpp connections, given equivalent inputs — same retry limits, same validation rules, same error conditions (this is the direct continuation of the prerequisite epic's own FR-007/FR-008).
- **FR-005**: The system MUST allow a workflow author to explicitly load a model into memory and explicitly unload a model from memory on a connected llama.cpp server.
- **FR-006**: The system MUST surface a clear, specific error when connected to a `llama-server` instance that isn't running in router mode (the endpoints this feature needs don't exist), rather than an unhelpful generic failure.

### Key Entities *(include if feature involves data)*

- **llama.cpp connection**: A configured connection to a local `llama-server` instance running in router mode (host + any authentication), implementing the same connection concept already established for Ollama.
- **Model status**: Reuses the existing status concept from the prerequisite feature, now populated with llama.cpp's full vocabulary rather than a narrowed subset.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A workflow author can connect to a llama.cpp server and get a chat response using the same node count and shape as connecting to Ollama (one connection node, one chat node) — no new nodes to learn for the chat path.
- **SC-002**: An existing workflow can be repointed from Ollama to llama.cpp by changing exactly one node (the connection node) — zero edits to any chat or model-management node.
- **SC-003**: Structured-output workflows behave identically (same validation guarantees, zero blank-required-field results) regardless of which backend is connected.
- **SC-004**: Model status reporting for llama.cpp surfaces all five status values where applicable — a strictly richer view than what Ollama can report through the same interface.

## Assumptions

- Workflow authors run their own local `llama-server` instance, launched in router mode (`--models-dir` or `--models-preset`), reachable over HTTP from the machine running ComfyUI; this feature does not install, configure, or launch that server.
- Non-router-mode `llama-server` usage (a single model launched with `-m`) is out of scope — router mode is required for the load/unload/status parity with Ollama that is this feature's whole point.
- GPU inference optimisation, quantisation tuning, authentication/TLS, and ComfyUI Manager registry listing are out of scope, consistent with the prerequisite Ollama epic's own non-goals.
- The `LLMProvider` protocol and generic nodes (`ChatCompletion`, `LLMModelSelector`, `LLMLoadModel`, `LLMUnloadModel`) already exist and are not modified by this feature — if llama.cpp's router mode needs a protocol capability that doesn't exist yet, that is a protocol change scoped as its own follow-up, not silently special-cased here.
