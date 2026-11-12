# ADR-011: pydantic-ai Agent harness behind `LLMProvider`, with a native-`/api/chat` Ollama model

## Status

> Accepted

_Date:_ 2026-11-12
_Deciders:_ darth-veitcher

---

## Context

comfydv's LLM nodes are one-shot chat functions. We want an *agent*: a node whose model calls tools (web search, web fetch, MCP servers) and loops
for several steps before it answers. It must use the same local backends that we already support (Ollama and llama.cpp router mode, via the
`LLMProvider` Protocol of ADR-007).

`pydantic-ai` is a runtime dependency since ADR-007. A tool-call loop of our own would re-implement
what it provides:

- the `Agent` loop and `UsageLimits`
- `MCPToolset` (FastMCP-based, stdio and HTTP transports)
- local web search and web fetch tools
- `TestModel` and `FunctionModel` for tests
 ADR-006's rejection of pydantic-ai was about dependency weight, and ADR-007 already
accepted that weight.

The catch: pydantic-ai's `OllamaModel` is an `OpenAIChatModel` over Ollama's
`/v1/chat/completions`. ADR-009 proved that this endpoint reloads the model at the default context
size on **every** call, discarding `num_ctx`. An agent's context grows with every tool result. Thus a silent 4096-token ceiling makes multi-step
runs unreliable, in exactly the situations where an agent must help.

## Decision

1. **Use `pydantic_ai.Agent` as the agent loop.** Do not hand-roll one.
2. **Extend `LLMProvider` with `agent_model(model, options) -> pydantic_ai.models.Model`.** Nodes
   stay provider-agnostic (ADR-007).
   - `LlamaCppProvider` returns `OpenAIChatModel` over `{host}/v1`.
   - `OllamaProvider` returns a new **`OllamaNativeModel`**. This is a `pydantic_ai.models.Model`
     subclass that implements `request()` over Ollama's native `/api/chat` through the existing
     aiohttp `_post_json`. It maps pydantic-ai messages to and from native `tools`/`tool_calls`,
     `thinking`, `images` and `options` (including `num_ctx`). ADR-004's aiohttp-only stance for
     Ollama is kept.
3. **MCP is the single tool mechanism, and a core dependency.** `pydantic-ai-slim[openai]` becomes
   `[openai,mcp]` in `pyproject.toml` and `requirements.txt`. Every tool reaches the agent through
   `MCPToolset`. comfydv's own tools (`web_fetch`, and `web_search` over SearXNG) are FastMCP servers under
   `src/comfydv/mcp/`. They are mounted **in-process** (no subprocess). Other MCP clients can also run
   them standalone.
4. **Tools travel as plain, hashable descriptors** on a new `LLM_TOOLS` socket, each naming an
   MCP source: built-in, HTTP URL, or named stdio server. Live toolsets and MCP connections are
   built per execution inside the agent runner and torn down when it finishes.
5. **stdio MCP servers are referenced by name only**, from a local config file outside the
   workflow. A shared workflow JSON must never be able to specify a command to execute.
6. **The agent ships as a new `Agent` node.** It is not a `tools` input on `ChatCompletion`, whose
   cache, refusal-retry and seed semantics assume one deterministic request.

## Consequences

**Easier:**
- Multi-step tool use, MCP and usage limits come from a maintained library, not from our code.
- `num_ctx` and the other native options apply to every agent step on Ollama.
- `OllamaNativeModel` gives a later path to re-express `chat()`/`chat_structured()` as "an agent
  with no tools", which would retire the two structured-output implementations ADR-009 accepted as debt.
- Agent nodes can be unit-tested against `TestModel`/`FunctionModel` without a live server.

**Harder / constrained:**
- We own a pydantic-ai `Model` adapter and must track pydantic-ai's message types across upgrades.
  Mitigations: pin the version and keep contract tests on the message mapping.
- The `[mcp]` extra adds 34 packages / ~46 MB to every install (measured, pydantic-ai-slim 2.9.0),
  including `starlette`, `uvicorn` and `cryptography`. Those carry pin-conflict risk with other
  ComfyUI custom-node packs, so the first bullet must smoke-test an install into a real ComfyUI
  environment. `rich` arrives transitively, but comfydv code must not import it (ADR-001).
- Tool-calling quality depends on the local model. We fail fast on models whose Ollama
  `/api/show` capabilities lack `tools`.
- Tool output is untrusted input to the model (prompt injection). v1 is limited to read-only
  tools plus user-configured MCP servers, with no in-graph human approval.

**Debt introduced:**
- Streaming is not implemented in `OllamaNativeModel` v1 (`request()` only).
- `updated_history` drops tool-call turns in v1. They are surfaced in a `trace` output instead.

## Considered Alternatives

### Alternative A: pydantic-ai's built-in `OllamaModel` (OpenAI-compatible)

**Why rejected:** It is subject to ADR-009's per-call context reset, which is fatal for growing agent
contexts. The only workaround is a server-side `OLLAMA_CONTEXT_LENGTH`. That moves configuration out of the graph,
and it contradicts ADR-005 (the client node is the single source of connection config).

### Alternative B: Hand-rolled tool loop on top of `LLMProvider.chat()`

**Why rejected:** It re-implements tool schema generation, argument validation/retry, usage limits
and MCP client handling. That is a large maintenance surface for no gain over a library we already ship.

### Alternative C: Built-in tools as plain pydantic-ai function tools, MCP only for external servers

**Why rejected:** It gives two tool code paths, with limits, tracing and error handling implemented
twice. Since MCP is mandatory and first-party MCP servers are planned anyway, authoring built-ins as
FastMCP servers costs one in-process round-trip per call. In return there is one integration path,
and the tools are reusable outside ComfyUI.

### Alternative D: MCP (and DuckDuckGo search) as optional extras

**Why rejected:** The maintainer decided MCP is mandatory. Optional extras would also mean
lazy-import branches and a degraded install path through ComfyUI-Manager, which installs
`requirements.txt` only. DuckDuckGo is dropped in favour of SearXNG.

### Alternative E: Add `tools` to the existing `ChatCompletion` node

**Why rejected (for now):** It mixes deterministic, cached single requests with non-deterministic
multi-step runs in one node. Convergence is still on the table once both run on `agent_model()`.

---

## Links

- Analysis: `project-management/Work/analysis/llm-agent-harness.md`
- Related ADRs: [ADR-012](ADR-012-agent-skills-as-on-demand-know-how-distinct-from-tools.md) (skills), [ADR-004](ADR-004-aiohttp-over-httpx-for-ollama.md), [ADR-005](ADR-005-ollama-host-config-via-client-node.md), [ADR-006](ADR-006-structured-ollama-output-tool-calling-not-pydantic-ai.md), [ADR-007](ADR-007-llm-provider-adapter-pattern.md), [ADR-009](ADR-009-native-structured-output-mode.md)
- External reference: pydantic-ai 2.9.0 (`pydantic_ai.models.Model`, `pydantic_ai.mcp.MCPToolset`, `pydantic_ai.capabilities`)
