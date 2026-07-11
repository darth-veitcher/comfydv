# Feature Specification: LLM Provider Abstraction

**Feature Branch**: `007-llm-provider-abstraction`

**Created**: 2026-07-11

**Status**: Draft

**Input**: User description: "Introduce a shared LLMProvider protocol for comfydv's LLM backend nodes so ComfyUI workflow authors can swap between local inference servers (starting with Ollama, with llama.cpp planned next) without changing their chat/model-management nodes. Migrate the existing Ollama integration onto generic nodes (client config, model list, load, unload, chat completion with optional structured/validated output) backed by this shared interface, per ADR-007."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect to a local inference server and get chat responses (Priority: P1)

As a ComfyUI workflow author, I want to point a single configuration node at my local LLM server and get chat responses through a generic chat node, so I can generate text without hardcoding a server address into every node that needs one.

**Why this priority**: This is the minimum viable path — without a working connection and a basic chat response, nothing else in this feature has value. It also directly replaces the most-used capability of the existing Ollama integration, so it carries the highest regression risk.

**Independent Test**: Wire a client configuration node into a chat node, run the workflow against a running local server, and confirm the chat node returns the model's text response.

**Acceptance Scenarios**:

1. **Given** a running local inference server and a workflow with a client node wired into a chat node, **When** the workflow executes, **Then** the chat node returns the model's text response.
2. **Given** a client node configured with an unreachable server address, **When** the workflow executes, **Then** the chat node reports a clear connection error rather than hanging indefinitely or crashing the workflow.
3. **Given** two chat nodes in the same workflow wired to the same client node, **When** the host address is changed on the client node, **Then** both chat nodes use the new address without being edited individually.

---

### User Story 2 - Get structured, validated output instead of parsing raw text (Priority: P1)

As a workflow author, I want to describe the shape of data I need and turn on structured output for a chat node, so downstream nodes receive individually typed fields I can trust are present and non-empty, instead of me parsing free text myself.

**Why this priority**: This is an existing, relied-upon capability of the current Ollama integration (structured output with retry-on-invalid-response). Preserving it exactly is required for this migration to be considered safe, so it's equal priority to basic chat.

**Independent Test**: Enable structured output on a chat node with a schema describing two or three fields, run the workflow against a model, and confirm each schema field is exposed as its own typed output socket with a valid value.

**Acceptance Scenarios**:

1. **Given** a chat node with structured output enabled and a valid schema, **When** the workflow executes and the model responds correctly, **Then** each schema field is available as its own typed output, and no required field is blank.
2. **Given** a model that returns invalid, incomplete, or empty-required-field output, **When** the workflow executes, **Then** the node automatically retries the request up to a configured limit.
3. **Given** a model that continues to return invalid output after all retries are exhausted, **When** the workflow executes, **Then** the node fails with a clear, specific error rather than silently passing through invalid or partial data.

---

### User Story 3 - Manage which models are resident in memory (Priority: P2)

As a workflow author running models locally, I want to see which models are currently loaded, loading, or unloaded, and explicitly load or unload a model, so I can control memory usage on my machine without leaving ComfyUI or using a separate terminal.

**Why this priority**: Valuable and already present in the current Ollama integration, but a workflow can still generate output without ever calling load/unload explicitly (servers can auto-load on first use) — so this is lower risk to defer than basic chat.

**Independent Test**: Use a model-listing node against a running server, confirm it shows each available model with a current status; use load/unload nodes against one model and confirm its reported status changes accordingly.

**Acceptance Scenarios**:

1. **Given** a running local server with at least one available model, **When** a workflow author uses the model-listing node, **Then** they see each available model along with its current status.
2. **Given** a model that is not currently loaded, **When** a workflow author runs the load-model node against it, **Then** the model becomes loaded and is then usable by the chat node.
3. **Given** a model that is loaded and idle, **When** a workflow author runs the unload-model node against it, **Then** the model is freed from memory and its reported status updates accordingly.

---

### User Story 4 - Reconnect an existing workflow after upgrading (Priority: P3)

As an existing user of the current Ollama nodes, when I open a workflow I saved before this change, I want it to be clear which new node replaces each renamed one, so I can reconnect my workflow with minimal effort and get the same results as before.

**Why this priority**: This is migration friction, not new capability — it matters for a good upgrade experience but doesn't block anyone building a new workflow from scratch, so it's the lowest priority of the four.

**Independent Test**: Open a workflow saved against the current Ollama-specific node names, follow the provided migration guidance to reconnect it to the new generic nodes, and confirm it produces the same output as before, given the same inputs and model.

**Acceptance Scenarios**:

1. **Given** a saved workflow using the current Ollama-specific node and connection-socket names, **When** it is opened after upgrading, **Then** ComfyUI reports the now-missing node types (standard ComfyUI behavior for renamed nodes), and documentation identifies the replacement node for each one.
2. **Given** a workflow that has been reconnected to the new generic nodes, **When** it executes with the same inputs and model as before the upgrade, **Then** it produces equivalent output.

---

### Edge Cases

- What happens when the configured server address is unreachable at the moment a model-listing, load, or unload node runs (not just the chat node)?
- What happens when a workflow author supplies an invalid or malformed schema to structured output, rather than an invalid model response?
- What happens when the connected server does not support structured/validated output at all?
- What happens to an in-flight chat request if the model it depends on is unloaded by another node in the same workflow run?
- What happens when a workflow author tries to wire a pre-upgrade Ollama-specific node's output into a new generic node, or vice versa? (Expected: ComfyUI's own type-checking refuses the connection, since the socket types differ — this is the intended, safe failure mode, not a bug to work around.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow a workflow author to configure a connection to a local inference server once and reuse that single configuration across multiple nodes in the same workflow.
- **FR-002**: The system MUST allow a workflow author to request either free-text or schema-validated structured output from the same chat node, choosing per request.
- **FR-003**: When structured output is requested, the system MUST validate the response against the supplied schema and MUST NOT deliver output to downstream nodes where a required field is missing or empty.
- **FR-004**: When validation fails, the system MUST retry the request automatically up to a configurable limit before reporting a clear, actionable error that identifies the model, the number of attempts made, and a snippet of the last invalid response.
- **FR-005**: The system MUST allow a workflow author to list available models on a connected server along with each model's current residency status.
- **FR-006**: The system MUST allow a workflow author to explicitly load a model into memory and explicitly unload a model from memory.
- **FR-007**: The system's chat and model-management nodes MUST behave identically regardless of which supported local inference server is connected, given equivalent inputs.
- **FR-008**: The existing chat and structured-output behavior for the currently-supported local inference server (Ollama) MUST be unchanged in outcome after this migration — same retry limits, same validation rules, same error conditions — since this feature changes the underlying mechanism, not the capability.
- **FR-009**: The system MUST document, for each node type renamed or removed by this change, which new node replaces it.

### Key Entities *(include if feature involves data)*

- **Provider connection**: A configured connection to one local inference server (address and any authentication), created once and reused by every model-management and chat node that needs it.
- **Model**: An inference model known to a provider connection, identified by name, with a current residency status (e.g., unloaded, loading, loaded, and — on servers that support it — sleeping or downloading).
- **Chat request/response**: A request for a model's output, optionally carrying a schema describing the required shape of a structured response, and the corresponding validated or free-text result.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A workflow author can go from no nodes to a working chat response using no more than two nodes (one connection node, one chat node).
- **SC-002**: Structured-output workflows never deliver a blank or missing required field to a downstream node — every request either produces fully valid data or a clear error, with zero silent partial results.
- **SC-003**: Existing example/reference workflows built against the current Ollama nodes remain reproducible on the new nodes with equivalent output, after a workflow author reconnects the renamed nodes.
- **SC-004**: Adding support for a second local inference server (planned as a follow-on feature) requires no visible change to chat or model-management node behavior — only a new connection node is needed.

## Assumptions

- Workflow authors run their own local inference server (e.g., Ollama) reachable over HTTP from the machine running ComfyUI; this feature does not host, install, or manage that server.
- Users with workflows saved against the current Ollama-specific node and socket names will need to manually reconnect them after upgrading. This is an accepted, intentional breaking change (confirmed 2026-07-11), not a defect — see FR-009 for the mitigation (documented replacement mapping), not automatic migration.
- Support for a second local inference server (llama.cpp) is planned as a separate, follow-on feature and is out of scope here — this feature only needs to prove the shared design works end-to-end for one real backend (Ollama).
- Structured-output schemas remain limited to flat object shapes with typed properties, consistent with what the current Ollama integration already supports — deeper nested schemas are unaffected by (neither improved nor degraded by) this change.
- No new observability/tracing capability is introduced for workflow authors as part of this feature, even though the underlying mechanism change makes it feasible to add later.
