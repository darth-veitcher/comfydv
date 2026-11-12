# Analysis: an agentic harness for comfydv's LLM nodes

_Date:_ 2026-11-12 · _Phase:_ DESIGN (pre-spec) · _Decision record:_ [ADR-011](../../ADRs/ADR-011-pydantic-ai-agent-harness-with-native-ollama-model.md) (Proposed)

The goal is to turn the current one-shot "chat function" into an **agent**: a model
that can call tools (web search, web fetch, MCP servers), observe the results, and
loop for several steps before answering. All of this stays inside a ComfyUI node graph.

---

## 1. Where we are today

| Layer | What exists | Notes |
|---|---|---|
| Backends | `OllamaProvider`, `LlamaCppProvider` (`src/comfydv/_llm/`) | Both implement the `LLMProvider` Protocol (ADR-007). So yes, we support both. |
| Generic nodes | `ChatCompletion`, `LLMModelSelector`, `LLMLoadModel`, `LLMUnloadModel` | Already provider-agnostic. They take an `LLM_CLIENT` input. |
| Backend nodes | `OllamaClient`, `LlamaCppClient` | Each is correctly backend-specific. |
| "Ollama"-named but generic | 9× `OllamaOption*`, 3× `OllamaHeader*`, `OllamaDebugHistory`, `OllamaHistoryLength` | These feed **both** providers. The names are wrong. |
| Socket types | `LLM_CLIENT`, `OLLAMA_OPTIONS`, `OLLAMA_HISTORY`, `OLLAMA_HEADERS` | Same naming debt. |
| Categories | `dv/ollama`, `dv/ollama/options`, `dv/ollama/headers`, `dv/llamacpp` | |
| Module layout | `src/comfydv/ollama.py` (~1150 lines) holds nearly every LLM node, generic ones included | |
| pydantic-ai | `pydantic-ai-slim[openai]==2.9.0` is **already a runtime dependency** (ADR-007) | Only the llama.cpp structured-output path uses it (`_llm/chat.py`). |

The one workflow in the repo (`workflows/ltx-i2v-pipeline.json`) uses `ChatCompletion` ×6,
`OllamaClient`, `OllamaOptionMaxTokens`, `OllamaOptionExtraBody` and
`OllamaOptionDisableThinking`. Whatever rename we do has to keep that file loading.

## 2. What pydantic-ai 2.9 gives us (verified against the installed package)

- **`Agent` loop**: a multi-step tool-call → observe → repeat loop. It includes
  `UsageLimits` (request/tool-call/token caps), message history, output validation
  (`NativeOutput`/`ToolOutput`), and `agent.iter()` for observing each step.
- **Capabilities** (`pydantic_ai.capabilities`): `WebSearch`, `WebFetch`, `MCP`, `Thinking`, and others.
  Each one is a "native or local" tool. Native tools (hosted search, hosted MCP) only work on
  cloud providers. Against local models we always want the **local** side.
- **Common tools**: `duckduckgo_search_tool` (needs the `duckduckgo` extra, `ddgs`), `tavily`,
  `exa`, and `web_fetch_tool` (needs `markdownify`; has SSRF protection built in via `_ssrf.safe_download`).
- **MCP**: `pydantic_ai.mcp.MCPToolset`. It is built on FastMCP and supports stdio,
  streamable-HTTP and SSE transports, plus `load_mcp_toolsets()` for multi-server JSON configs.
- **Custom models**: a `Model` subclass only has to implement `request()` (plus the
  `model_name` and `system` properties). The non-streaming path is small.
- **Testing**: `TestModel` and `FunctionModel` let us unit-test agent nodes without any server.

### The constraint that shapes everything

`pydantic_ai.models.ollama.OllamaModel` is an **`OpenAIChatModel` over Ollama's
`/v1/chat/completions`**. ADR-009 proved that this endpoint **reloads the model at the
default context size on every call**, throwing away `num_ctx`. A chat call can survive that.
An agent cannot. Tool results (search snippets, fetched pages, MCP payloads) pile up in
the context with every step, and at a 4096-token default the agent quietly truncates its own
working memory by step 2 or 3.

**So the Ollama side needs a small native `Model` adapter over `/api/chat`.** Ollama's native
endpoint supports `tools`, returns `message.tool_calls`, keeps `thinking` separate, honours
`options` (`num_ctx` included), takes `images` and supports `format`. llama.cpp has no such
problem (context is fixed when the server launches), so `OpenAIChatModel` works unchanged there.

## 3. Proposed architecture

```
              ┌────────────── ComfyUI graph ───────────────┐
 OllamaClient ─┐                                            │
LlamaCppClient ┴─► LLM_CLIENT ─┐                            │
                               ▼                            │
 Tool: Web Search ─┐       ┌─────────┐   response (STRING)   │
 Tool: Web Fetch  ─┼─TOOLS►│  Agent  │── history  (LLM_HISTORY)
 Tool: MCP Server ─┘       │  node   │── trace    (STRING)   │
 LLM Option: … ─── OPTIONS►│         │── [structured fields] │
 image / history ─────────►└─────────┘                       │
              └─────────────────────────────────────────────┘
                               │ LLMProvider.agent_model(model, options)
                               ▼
        ┌──────────── comfydv._llm (no ComfyUI imports) ────────────┐
        │ OllamaProvider   → OllamaNativeModel(pydantic_ai Model)  │  aiohttp → /api/chat
        │ LlamaCppProvider → OpenAIChatModel(base_url=…/v1)        │  openai SDK (exists)
        │ tools/  → descriptor → pydantic-ai Tool / Toolset builder │
        │ agent.py → run_agent(model, tools, limits, on_status)     │  pydantic_ai.Agent
        └───────────────────────────────────────────────────────────┘
```

### 3.1 Protocol extension (ADR-007 stays intact)

Add one method to `LLMProvider`:

```python
def agent_model(self, model: str, options: dict | None = None) -> pydantic_ai.models.Model: ...
```

Nodes never branch on the provider type, which is the point of ADR-007. Each provider decides
how it speaks to pydantic-ai. This is also the seam a later convergence would go through. If
`OllamaNativeModel` proves itself, `chat()` and `chat_structured()` for both providers can be
re-expressed as "an agent with no tools". That would retire the duplicated structured-output
paths that ADR-009 accepted as debt.

### 3.2 Tools as composable sockets: the ComfyUI-native idiom

Tools chain the same way `OllamaHeader*` and the option nodes already do:

- New socket type `LLM_TOOLS`. Each tool node has an optional `tools` input and appends itself.
- What travels on the socket is a **plain, hashable descriptor** (`{"kind": "web_search",
  "backend": "searxng", "url": …}`), not a live pydantic-ai object or MCP connection. Live objects
  are built inside `run_agent()` for the duration of one execution. That keeps node caching
  sane and means no subprocess or connection outlives a queue run.
- Initial tool nodes:

| Node | Backend | New deps |
|---|---|---|
| **Tool — Web Fetch** | aiohttp + stdlib HTML→text. Private and loopback IPs blocked by default, with a toggle (local-first users may want their LAN). | none |
| **Tool — Web Search** | **SearXNG** (self-hosted, JSON API, plain aiohttp) by default. DuckDuckGo via the optional `comfydv[search]` extra. | none (SearXNG) |
| **Tool — MCP Server** | `MCPToolset`. HTTP by URL. **stdio only by name from a local config file** (see §4). | optional `comfydv[mcp]` |

SearXNG fits the project's local-first stance: it sits next to Ollama in `docker-compose`, needs
no API keys and is reached over aiohttp, which keeps ADR-004 intact. DuckDuckGo scraping is
fragile and rate-limited, so it is opt-in rather than the default.

### 3.3 The Agent node

Inputs: `client`, `model`, `prompt`, `system`/instructions, `tools` (optional), `options`,
`history`, `image`, `max_steps` (→ `UsageLimits.request_limit`), `max_tool_calls`,
`timeout_secs`, and later `structured_output`/`output_schema` (reusing `ChatCompletion`'s
dynamic-socket machinery).

Outputs: `response`, `updated_history`, `model_name`, `trace`.

- `trace` is a readable step log ("step 2 → web_search('…') → 5 results").
- Live progress uses the existing `on_status` → `send_progress_text` hook, so each tool call
  shows on the node while it runs. Cheap, and exactly the visibility an agent needs.
- `updated_history` stays the existing role/content dict list, which keeps it chain-compatible
  with `ChatCompletion`. The tool-call messages go into `trace`, not into history (v1).
- **No response cache.** Agent runs hit the live web, so they are non-deterministic.
- Fail fast when a model has no tool support: Ollama's `/api/show` reports `capabilities: ["tools", …]`.

**Why a separate node rather than adding `tools` to `ChatCompletion`:** `ChatCompletion`'s
cache, refusal-retry and seed semantics assume one deterministic request. Agent runs break all
three assumptions. Keep the proven node stable, build `Agent` next to it, and merge them later
only once the internals have converged (§3.1).

## 4. Safety: the part most likely to bite

1. **Workflows are shared files.** A stdio MCP server is "run this command". If a workflow JSON
   can define `command: …`, then loading someone else's workflow is remote code execution.
   Rule: **workflow JSON may only *name* a stdio server.** Definitions live in a local config
   file (for example `<ComfyUI user dir>/comfydv/mcp.json`, standard `mcpServers` format, read with
   `load_mcp_toolsets`). HTTP MCP servers by URL are acceptable.
2. **Prompt injection via tool output.** Fetched pages and search results go straight into the
   model's context. With read-only tools the damage is bounded. Every write-capable MCP server
   a user adds widens it. Document this. Shell and code-exec tools are an explicit non-goal.
3. **Runaway loops.** `UsageLimits` (steps, tool calls, tokens), a per-tool timeout and an overall
   `timeout_secs` are mandatory, with conservative defaults.
4. **Human approval** (pydantic-ai's `ApprovalRequiredToolset`) does not fit ComfyUI's
   non-interactive execution model. It is out of scope for v1. The allowlist and limits above replace it.

## 5. Renaming and reorganisation

Principle: **name by role, not by backend.** Only `OllamaClient` and `LlamaCppClient` are
backend-specific, so only they keep backend names.

| Kind | Breaks saved workflows? | Proposal |
|---|---|---|
| Categories | No | `dv/llm`, `dv/llm/clients`, `dv/llm/options`, `dv/llm/headers`, `dv/llm/history`, `dv/llm/tools` |
| Display names | No | "LLM Option — Temperature", "LLM Header — Bearer Token", "Agent", "Tool — Web Search", … |
| Python modules | No | Split `ollama.py` into `src/comfydv/llm/{clients,chat,agent,models,options,headers,history,tools}.py` |
| Node class keys | **Yes** | `OllamaOptionSeed` → `LLMOptionSeed` etc. Keep each old key registered as a thin subclass with `DEPRECATED = True` (ComfyUI hides deprecated nodes from search but still loads them). Remove after one minor release. |
| Socket types | **Yes** (link type checks) | `OLLAMA_OPTIONS/HISTORY/HEADERS` → `LLM_OPTIONS/HISTORY/HEADERS`. Needs a spike: ComfyUI's frontend may accept comma-joined type unions on inputs, which would allow a zero-break transition. If not, it is a single breaking change, documented in `MIGRATION_MAP` the way ADR-007 did it. |

This rename is **independent of the agent work** and should land first, as its own small spec,
so the Agent and Tool nodes are created in their final home rather than renamed straight after.

## 6. Dependencies (ADR-003 / ADR-004)

- Core needs **no new runtime deps**. `pydantic-ai-slim[openai]` is already present.
  `OllamaNativeModel`, Web Fetch and SearXNG search all run on aiohttp.
- `mcp` (fastmcp + mcp SDK + server stack) and `duckduckgo` are heavy. A scratch install of
  `pydantic-ai-slim[openai,mcp,duckduckgo]` came to ~116 MB across 136 packages. That is a real
  conflict risk inside a ComfyUI venv, so these become **optional extras** (`comfydv[mcp]`,
  `comfydv[search]`). Tool nodes lazy-import them and raise an actionable "install
  `comfydv[mcp]`" error. ComfyUI-Manager installs `requirements.txt` only, so the README must
  document the extras.

## 7. Proposed sequencing (tracer bullets)

| # | Spec | Bullet | Demo |
|---|---|---|---|
| 0 | `010-llm-node-naming` | Categories, display names, module split, deprecated aliases, socket-type spike | Old workflow loads; new names appear in search |
| 1 | `011-llm-agent` | `LLMProvider.agent_model()`; `OllamaNativeModel` (non-streaming, tools, think, options); `OpenAIChatModel` for llama.cpp; `Agent` node; **Tool — Web Fetch**; limits; live progress; `trace` | "Summarise <url>" on a local qwen3 via Ollama, every step visible on the node |
| 2 | 011 | **Tool — Web Search** (SearXNG; DuckDuckGo extra); `searxng` service in `docker-compose.dev.yml` | "What changed in llama.cpp this week?" → search → fetch → answer |
| 3 | 011 | **Tool — MCP Server** (`comfydv[mcp]`; HTTP by URL; stdio by name from config) | Agent uses a local filesystem/time MCP server |
| 4 | 011 | Structured output + image input on `Agent` (`format` on the native model; reuse dynamic sockets) | Vision agent returns typed fields into FormatString |
| 5 | later | Converge `ChatCompletion` onto `agent_model()` (no tools), retiring ADR-009's duplication, only once parity is proven | Same workflow, one code path |

**Future** (into `Work/planning/future-features.md` once agreed): sub-agents as tools (Agent output →
`LLM_TOOLS`), streaming tokens to the UI, persistent agent memory, cloud providers
(OpenAI/Anthropic) as additional `LLM_CLIENT`s, where native web search and MCP *would* apply.

## 8. Open decisions for the maintainer

1. **Rename back-compat:** deprecated aliases for one release (recommended) or a clean break with `MIGRATION_MAP`?
2. **Default search backend:** SearXNG (recommended, self-hosted, no deps) or DuckDuckGo (zero setup, extra deps, fragile)?
3. **MCP stdio:** accept the "named servers from local config only" rule, or allow HTTP-only MCP in v1?
4. **Spec layout:** rename as its own spec 010 first (recommended), or fold it into the agent epic?
