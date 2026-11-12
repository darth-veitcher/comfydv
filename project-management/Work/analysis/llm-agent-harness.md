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
        │ tools.py → descriptor → MCPToolset (built-in | http | stdio) │
        │ skills.py → Skills capability (catalog + load_skill)      │  SKILL.md, text only
        │ agent.py → run_agent(model, tools, limits, on_status)     │  pydantic_ai.Agent
        └───────────────────────────────────────────────────────────┘
        ┌──────────── comfydv.mcp (first-party FastMCP servers) ────┐
        │ web.py → web_fetch, web_search(SearXNG)                   │  in-process, or
        │ …future comfydv MCP servers                               │  `python -m comfydv.mcp.web`
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
- **MCP is the single tool mechanism** (maintainer decision, 2026-11-12: MCP support is
  mandatory, and comfydv is expected to grow its own MCP servers). Every tool an agent
  sees reaches it through `pydantic_ai.mcp.MCPToolset`, including comfydv's built-in tools:
  - **Built-in tools are authored as FastMCP servers** in `src/comfydv/mcp/` (for example
    `comfydv.mcp.web` exposing `web_search` and `web_fetch`). `MCPToolset` accepts a `FastMCP`
    instance directly, so built-ins are **mounted in-process**: no subprocess, no config file,
    no port. The same module also runs standalone (`python -m comfydv.mcp.web`), so other MCP
    clients (Claude Desktop, other agents) can use comfydv's tools outside ComfyUI.
  - This keeps tool integration in one place (DRY): limits, timeouts, error handling, tracing and
    tool-name prefixing are written once for "an MCP toolset", not once per tool kind. Adding a
    first-party tool means adding a function to a FastMCP server, not a new code path.
  - The cost is a small in-process MCP round-trip per tool call. That is negligible next to an
    LLM step.
- Initial tool nodes. Each emits a descriptor naming an MCP source:

| Node | MCP source | Notes |
|---|---|---|
| **Tool — Web Fetch** | built-in `comfydv.mcp.web` (in-process) | aiohttp + stdlib HTML→text. Private and loopback IPs blocked by default, with a toggle (local-first users may want their LAN). |
| **Tool — Web Search** | built-in `comfydv.mcp.web` (in-process) | **SearXNG** JSON API over aiohttp (maintainer decision). Instance URL is a node input. |
| **Tool — MCP Server** | external | Streamable-HTTP/SSE by URL (+ optional headers, reusing `LLM_HEADERS`). **stdio only by name from a local config file** (see §4). Optional `allowed_tools` filter. |

SearXNG fits the project's local-first stance: it sits next to Ollama in `docker-compose`, needs
no API keys and is reached over aiohttp, which keeps ADR-004 intact. DuckDuckGo is out of scope
for v1. If a zero-setup fallback is wanted later, it is one more function on `comfydv.mcp.web`.

### 3.3 Skills, and how they differ from tools

Decision record: [ADR-012](../../ADRs/ADR-012-agent-skills-as-on-demand-know-how-distinct-from-tools.md) (Proposed).

**The delineation, in one line: a tool *does* something; a skill *tells the model how* to do something.**

| | **Tool** | **Skill** |
|---|---|---|
| What it is | An action: a typed function the model calls | Know-how: instructions + reference files, written for the model |
| Executes code? | Yes (on an MCP server) | **Never.** Pure text. Any `scripts/` in a skill folder are not run (no code-exec tool, by design). |
| Side effects / I/O | Yes (network, files, APIs) | None |
| Enters the context as | A schema (name, description, parameters) every step; results when called | A one-line **catalog entry** (name + description) every step; the **body only when loaded** (progressive disclosure) |
| Format | MCP tool | [Agent Skills](https://agentskills.io) `SKILL.md` folder (YAML frontmatter `name`, `description`) — the same format Claude, Cursor, Codex etc. use, so existing skills drop in |
| Socket / category | `LLM_TOOLS` · `dv/llm/tools` | `LLM_SKILLS` · `dv/llm/skills` |
| Relationship | — | A skill may **declare** the tools it expects (`requires-tools: [web_search, web_fetch]` in frontmatter). It never **contains** tools. If a required tool isn't wired, the Agent node fails fast with a clear message. |

**How skills differ from the system prompt:** the system prompt is always fully in context. A skill
costs one catalog line until the model decides it's relevant and loads it. That's what lets a
graph offer ten skills to a model with an 8k context.

**Mechanism (pydantic-ai):** one `Skills` capability (`AbstractCapability`) per agent run:

- `get_instructions()` → the skill catalog ("Available skills: `web-research` — how to research a
  question with search + fetch and cite sources; …"), plus one sentence telling the model to
  call `load_skill` before acting on a matching task.
- `get_toolset()` → two **internal** tools: `load_skill(name)` (returns the `SKILL.md` body) and
  `read_skill_file(name, path)` (supporting files, resolved strictly inside the skill folder).
  These are the skill system's plumbing, not user tools. They never appear on `LLM_TOOLS`, and the
  `trace` output shows them as `📘 loaded skill: web-research`, distinct from `🔧 tool calls`.
- `mode` per skill: `on_demand` (default, progressive disclosure) or `always` (body inlined into
  instructions). `always` is the escape hatch for small models whose tool calling is too weak to
  reliably call `load_skill`.

**Skill sources** (each a node emitting `LLM_SKILLS`, chainable):

| Node | Source | Notes |
|---|---|---|
| **Skill — Library** | A combo of skills found in the configured skill roots: `<ComfyUI user dir>/comfydv/skills/` and the skills comfydv ships in `src/comfydv/skills/` | The workflow *names* a skill. It cannot point at an arbitrary path, so a shared workflow can't read `~/.ssh` via `read_skill_file`. |
| **Skill — Inline** | `name`, `description` and a multiline `instructions` widget on the node | A skill authored in the graph. It's just text, so it is safe to share. |
| **Skill — from MCP** | An MCP server exposing skills as `skill://` resources (FastMCP's `SkillsProvider`) | Lets comfydv's own MCP servers ship tools **and** the skills that teach them. The **Tool — MCP Server** node gets a second `skills` output, so one server definition can feed both sockets. |

**Shipped built-in skill:** `web-research` (`requires-tools: [web_search, web_fetch]`). It
demonstrates the split on day one: the MCP server provides the abilities, and the skill provides
the method (query reformulation, fetch the top N, cross-check, cite URLs).

### 3.4 The Agent node

Inputs: `client`, `model`, `prompt`, `system`/instructions, `tools` (optional), `skills` (optional), `options`,
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
5. **Skills are trusted instructions.** A skill is text, but it is text the model is told to *follow*.
   A malicious skill is a prompt injection with a head start. Library skills come only from local
   skill roots the user controls. Skills from a third-party MCP server carry that server's trust
   level. Skill files are never executed, and `read_skill_file` cannot escape the skill folder.

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

- **MCP is a core runtime dependency** (maintainer decision). `pydantic-ai-slim[openai]` becomes
  `pydantic-ai-slim[openai,mcp]` in both `pyproject.toml` and the hand-authored
  `requirements.txt` (ADR-003). No optional extras, no lazy-import branches.
- Measured cost (clean venvs, pydantic-ai-slim 2.9.0): `[openai]` = 28 packages / 44 MB;
  `[openai,mcp]` = 62 packages / 90 MB, i.e. **+34 packages, +46 MB**. The additions are
  `fastmcp-slim`, `mcp`, `mcp-types`, `starlette`, `uvicorn`, `sse-starlette`, `pydantic-settings`,
  `jsonschema`, `cryptography`, `authlib`, `pyjwt`, `rich`, `python-dotenv` and related packages.
  - **Conflict risk** inside a ComfyUI venv sits mainly in `starlette`/`uvicorn`/`cryptography`
    pins shared with other custom-node packs. The first implementation bullet must do an install
    smoke test into a real ComfyUI environment (the `docker/` harness).
  - `rich` arrives transitively. ADR-001 removed it as *our* dependency, and nothing in comfydv
    may import it. ADR-001's NullHandler/stdlib-logging stance is unaffected.
- `OllamaNativeModel`, Web Fetch and SearXNG search all run on aiohttp. Beyond the MCP stack,
  they add nothing.

## 7. Proposed sequencing (tracer bullets)

| # | Spec | Bullet | Demo |
|---|---|---|---|
| 0 | `010-llm-node-naming` | Categories, display names, module split, deprecated aliases, socket-type spike | Old workflow loads; new names appear in search |
| 1 | `011-llm-agent` | `[mcp]` dep + ComfyUI install smoke test; `LLMProvider.agent_model()`; `OllamaNativeModel` (non-streaming, tools, think, options); `OpenAIChatModel` for llama.cpp; `Agent` node; in-process `comfydv.mcp.web` with **web_fetch**; **Tool — Web Fetch**; limits; live progress; `trace` | "Summarise <url>" on a local qwen3 via Ollama, every step visible on the node. The MCP path is proven on day 1. |
| 2 | 011 | **web_search** on `comfydv.mcp.web` (SearXNG) + **Tool — Web Search**; `searxng` service in `docker-compose.dev.yml` | "What changed in llama.cpp this week?" → search → fetch → answer |
| 3 | 011 | **Skills**: `Skills` capability, `LLM_SKILLS` socket, **Skill — Library** + **Skill — Inline**, `requires-tools` check, built-in `web-research` skill | The same question answered better with `web-research` wired: the trace shows `📘 loaded skill` before the `🔧` calls |
| 4 | 011 | **Tool — MCP Server**: external servers (HTTP by URL with headers; stdio by name from config), with a `skills` output (`skill://` resources) | Agent uses a third-party MCP server's tools and skills alongside the built-ins |
| 5 | 011 | Structured output + image input on `Agent` (`format` on the native model; reuse dynamic sockets) | Vision agent returns typed fields into FormatString |
| 6 | later | Converge `ChatCompletion` onto `agent_model()` (no tools), retiring ADR-009's duplication, only once parity is proven | Same workflow, one code path |

**Future** (into `Work/planning/future-features.md` once agreed): sub-agents as tools (Agent output →
`LLM_TOOLS`), streaming tokens to the UI, persistent agent memory, cloud providers
(OpenAI/Anthropic) as additional `LLM_CLIENT`s, where native web search and MCP *would* apply.

## 8. Open decisions for the maintainer

Resolved (2026-11-12):

- ✅ **MCP is mandatory.** It is a core dependency, not an extra, and comfydv will grow its own servers. §3.2 follows from this: MCP is the single tool mechanism, and built-ins are in-process FastMCP servers.
- ✅ **Search backend: SearXNG.** DuckDuckGo is dropped from v1.
- ✅ **Skills are first-class and distinct from tools** (§3.3, ADR-012): tools act, skills instruct. Skills are text-only `SKILL.md` folders, progressively disclosed, with their own socket and node category.

Still open:

1. **Rename back-compat:** deprecated aliases for one release (recommended) or a clean break with `MIGRATION_MAP`?
2. **MCP stdio:** accept the "named servers from local config only" rule (recommended), or allow stdio definitions in the workflow?
3. **Spec layout:** rename as its own spec 010 first (recommended), or fold it into the agent epic?
4. **Skill scripts:** never execute `scripts/` inside skill folders (recommended for v1, as there's no code-exec tool), or plan a sandboxed executor later?
