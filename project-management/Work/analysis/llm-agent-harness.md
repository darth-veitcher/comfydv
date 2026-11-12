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
        │ skills.py → Skills capability (catalog + load_skill)      │  SKILL.md
        │ sandbox.py → Monty: CodeMode + run_skill_script            │  exits = wired tools only
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
| Executes code? | Yes (on an MCP server), with real host authority | **Never acts by itself.** Text, plus optional `scripts/*.py` that run only in the **Monty sandbox** (§3.4), which can reach the world only through wired tools. |
| Side effects / I/O | Yes (network, files, APIs) | None of its own; only via tools |
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
- `get_toolset()` → **internal** tools: `load_skill(name)` (returns the `SKILL.md` body) and
  `read_skill_file(name, path)` (supporting files, resolved strictly inside the skill folder).
  These are the skill system's plumbing, not user tools. They never appear on `LLM_TOOLS`, and the
  `trace` output shows them as `📘 loaded skill: web-research`, distinct from `🔧 tool calls`.
- `run_skill_script(name, script, args)`: a third internal tool that runs a skill's `scripts/*.py`
  in Monty (§3.4), with the skill folder mounted read-only.
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

### 3.4 The sandbox: Monty, for code mode and skill scripts

Decision record: [ADR-013](../../ADRs/ADR-013-monty-sandbox-code-mode-and-skill-scripts.md) (Proposed).
This supersedes this doc's earlier "never execute" stance, which the maintainer challenged on 2026-11-12.

The sandbox is a third concept, neither a tool nor a skill. **It is where code runs, and it has no
authority of its own.** Its only exits are the agent's wired tools, exposed as external functions.

| Concept | Is | Acts on the world? |
|---|---|---|
| **Tool** | an action (MCP) | **Yes**, the only thing that does |
| **Skill** | know-how (+ optional scripts) | No; its scripts can only call tools |
| **Sandbox** | an execution environment (Monty) | No; code inside it can only call tools |

Two uses, one sandbox:

1. **Code mode** (`execution: tool_calls | code_mode` on the Agent node, via
   `pydantic_ai_harness.CodeMode`). The model gets one `run_code` tool and writes Python that calls
   tools as async functions, for example `asyncio.gather(web_search(...), web_search(...))`. That turns
   N model steps into one. For a local model at tens of seconds per step, it is the largest latency
   lever we have. Default stays `tool_calls` until a live evaluation on target local models shows code
   mode is reliable for them (writing correct subset-Python is a harder ask than emitting a tool call).
2. **Skill scripts** (`run_skill_script`, §3.3). Skill folders are mounted read-only and scripts get
   the same tool functions. Scripts that need third-party packages or unsupported syntax fail Monty's
   pre-run type check with a clear error. `.sh` and other non-Python scripts never run.

**Verified live (scratch venv, 2026-11-12):** one `run_code` snippet made two parallel tool calls
(`[3, 2]`) in a single model step. `open("/etc/passwd")` → `PermissionError`; `os.environ` →
`RuntimeError`; `import socket` → rejected by the pre-run type check. Monty 1.6.0 has wheels for
Windows, macOS and Linux, needs no Docker, and runs each session in a worker subprocess, so a crash
can't take ComfyUI down.

**Limits:** language-level isolation, not OS-level (no seccomp/VM); a Monty bug is an escape, so pin
it and track its advisories. There are no third-party packages, and no classes with inheritance,
generators or `del`. Defaults: 30 s and 256 MiB per snippet, with a capped tool-call count, all
exposed on the node.

### 3.5 The Agent node

Inputs: `client`, `model`, `prompt`, `system`/instructions, `tools` (optional), `skills` (optional), `execution` (`tool_calls` | `code_mode`), sandbox limits, `options`,
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

1. **Workflows are shared files.** A stdio MCP server means "run this program on this computer". A
   workflow JSON must never be able to start one silently. The trust model that enforces this is
   in §4.1.
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
   level. Skill scripts run only in Monty (read-only mount, tools as the only exits), and
   `read_skill_file` cannot escape the skill folder.
6. **The sandbox is not a security boundary for tools.** Monty contains *code*; a tool still runs with
   full host authority. Code mode means the model can call tools in loops, so per-snippet tool-call caps
   and the run-level `UsageLimits` both apply.

### 4.1 MCP server trust model (proposed; maintainer asked for options, 2026-11-12)

Goal: Claude Code's pattern, with safe built-ins enabled by default and extended or overridden by
local config, plus **transparent, low-friction toggling from the UI and the workflow** (like
rgthree's group bypass toggles), without letting a shared workflow run code or leak data unannounced.

**Layers** (later layers override earlier ones; **deny always beats allow**):

| # | Layer | Where | Can add servers? | Can run local programs? |
|---|---|---|---|---|
| 1 | **Built-in** | shipped in `comfydv.mcp` (in-process FastMCP: `web`, …) | n/a | No (in-process, our code) |
| 2 | **User config** | `<ComfyUI user dir>/comfydv/mcp.json`, standard `mcpServers` format (paste-compatible with Claude Desktop/Code) | Yes: HTTP and stdio | Yes, because the user wrote it |
| 3 | **Managed config** (optional, later) | path from `COMFYDV_MCP_MANAGED`, for shared or multi-user ComfyUI hosts | Can **lock**: `allow`/`deny` lists, `allow_workflow_servers: false` | Policy only |
| 4 | **Workflow** | node widgets saved in the workflow JSON | Only *proposes*: inert until approved (below) | Never without approval |

**Rules:**

- **Toggling is free; adding is approved.** A workflow may turn any *already-trusted* server
  (layers 1–2, or previously approved) on or off, and narrow its tools, with no prompt. It's just
  names and booleans, like a bypass toggle. A workflow can only *widen* access up to what local
  config permits.
- **Workflow-carried definitions are approve-on-first-use, hash-pinned.**
  - Sharing a workflow that needs a server can carry that server's definition.
  - On load, ComfyUI shows an approval dialog with the exact URL, or the exact command, args and env
    variable *names*.
  - A stdio definition is flagged red: "runs a program on this computer".
  - Choices: **Approve & save to my config** / **Allow this session** / **Deny**.
  - An approval is stored locally, keyed by a SHA-256 of the definition. If a later version of the
    workflow changes one byte of the command or URL, it is pending again.
  - HTTP servers need approval too: a prompt-injected agent could send your data to one.
- **Headless runs fail closed.** A queue run via the API (`/prompt`, no browser to approve in)
  that references a pending or unknown server errors before the first model call. The error names
  the server and says how to approve it (add it to `mcp.json`).
- **Secrets never live in workflows.** Config values may reference `${ENV_VAR}`. A workflow-carried
  definition may name required variables but never contain their values. On export, headers and
  env values are stripped.
- **Per-tool narrowing.** Config `"tools": {"allow": [...], "deny": [...]}` per server. The node's
  `allowed_tools` widget can only narrow further.

**Making it visible (UI):**

- The **Tool — MCP Servers** node renders one chip per server:
  - name, plus a **source** badge (`built-in`, `user`, `approved`, `pending`)
  - a **transport** icon (⚡ in-process, 🌐 HTTP, 🖥️ stdio, meaning a local program)
  - an on/off toggle
  - Pending chips are red with a **Review** button, which opens the approval dialog.
- A toast appears on workflow load when it references unknown or pending servers.
- The Agent's `trace` output starts with the servers and tools actually available to that run, as an audit line.

**Options considered:**

| | Friction | Security | Verdict |
|---|---|---|---|
| A. Config-only (workflows can only name servers) | High: sharing a workflow means editing `mcp.json` by hand | Highest | Too much friction for sharing |
| **B. Layered + free toggles + hash-pinned approve-on-first-use; headless fails closed** | Low: one click per new server, never again unless it changes | High: nothing runs or connects unannounced | **Recommended** |
| C. Trust workflow HTTP servers, approve only stdio | Lowest | Medium: an injected agent can exfiltrate to a workflow-chosen URL | Rejected |

## 5. Renaming and reorganisation

Principle: **name by role, not by backend.** Only `OllamaClient` and `LlamaCppClient` are
backend-specific, so only they keep backend names.

| Kind | Breaks saved workflows? | Proposal |
|---|---|---|
| Categories | No | `dv/llm`, `dv/llm/clients`, `dv/llm/options`, `dv/llm/headers`, `dv/llm/history`, `dv/llm/tools` |
| Display names | No | "LLM Option — Temperature", "LLM Header — Bearer Token", "Agent", "Tool — Web Search", … |
| Python modules | No | Split `ollama.py` into `src/comfydv/llm/{clients,chat,agent,models,options,headers,history,tools}.py` |
| Node class keys | **Yes** | `OllamaOptionSeed` → `LLMOptionSeed` etc. **Clean break** (maintainer decision, 2026-11-12): no deprecated aliases. |
| Socket types | **Yes** (link type checks) | `OLLAMA_OPTIONS/HISTORY/HEADERS` → `LLM_OPTIONS/HISTORY/HEADERS`, in the same clean break. |

**Documenting the break** (required, because a clean break is only acceptable if nobody is surprised):
- Ship it as a **versioned release** through the release pipeline (§8), never as an unannounced change on the
  default branch that ComfyUI-Manager's git-clone installs track.
- `CHANGELOG.md` gets a **Breaking** section with the full old→new table. `MIGRATION_MAP` is extended
  with every renamed node and socket.
- The README "Upgrading a workflow" section gets the same table.
- `workflows/ltx-i2v-pipeline.json` is migrated in the same change.
- Optional but cheap: a `scripts/migrate_workflow.py` that rewrites node types and socket types in a
  saved workflow JSON using `MIGRATION_MAP`, so users don't have to rewire by hand.

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
- **pydantic-ai upgrade 2.9 → 2.68, pinned exactly** (ADR-013). `pydantic-ai-harness[codemode]==0.68.0`
  pins `pydantic-ai-slim==2.68.0` exactly, and the two move in lockstep. The full stack
  (`[openai,mcp]` + harness `[codemode]` + `pydantic-monty` 1.6.0) measured **142 MB / 67 packages**.
  An exact pin risks clashing with another node pack that pins pydantic-ai. The escape hatch is to drive
  `pydantic-monty` (`>=1.5,<2`) directly and drop the harness.
- Telemetry and phone-home behaviour (FastMCP tracing context and PyPI version check, stdout banners) is
  off by default via `comfydv/_llm/_telemetry.py`, and users can opt in ([ADR-014](../../ADRs/ADR-014-telemetry-off-by-default.md)).
- 2.68's `OllamaModel` is still OpenAI-compatible (`/v1`), so ADR-011's native model is still needed.
- `OllamaNativeModel`, Web Fetch and SearXNG search all run on aiohttp. Beyond the MCP stack,
  they add nothing.

## 7. Proposed sequencing (tracer bullets)

| # | Spec | Bullet | Demo |
|---|---|---|---|
| R | `010-release-pipeline` | **First, because everything after it ships through it.** `develop` branch; CI gate (ruff, ty, pytest) on PRs; static version + python-semantic-release; `main` → tag + GitHub Release + PyPI + Comfy Registry; `develop` → PyPI pre-releases (§8) | Merge to `develop` publishes `0.2.0.dev1` to PyPI, and `pip install comfydv` still gets the last stable release |
| 0 | `011-llm-node-naming` | **Clean break**: categories, display names, module split, node keys and socket types renamed; `MIGRATION_MAP`, CHANGELOG **Breaking** section, README table, migrated sample workflow, optional `scripts/migrate_workflow.py` | First versioned release with a documented break; the migrated `ltx-i2v-pipeline.json` loads |
| 1 | `012-llm-agent` | pydantic-ai 2.68 upgrade (regression-test `_llm/chat.py`) + `[mcp]` and harness `[codemode]` deps + ComfyUI install smoke test; `LLMProvider.agent_model()`; `OllamaNativeModel` (non-streaming, tools, think, options); `OpenAIChatModel` for llama.cpp; `Agent` node; in-process `comfydv.mcp.web` with **web_fetch**; **Tool — Web Fetch**; limits; live progress; `trace` | "Summarise <url>" on a local qwen3 via Ollama, every step visible on the node. The MCP path is proven on day 1. |
| 2 | 012 | **web_search** on `comfydv.mcp.web` (SearXNG) + **Tool — Web Search**; `searxng` service in `docker-compose.dev.yml` | "What changed in llama.cpp this week?" → search → fetch → answer |
| 3 | 012 | **Skills**: `Skills` capability, `LLM_SKILLS` socket, **Skill — Library** + **Skill — Inline**, `requires-tools` check, built-in `web-research` skill | The same question answered better with `web-research` wired: the trace shows `📘 loaded skill` before the `🔧` calls |
| 3b | 012 | **Sandbox**: `execution: code_mode` on Agent (`CodeMode`, default stays `tool_calls`), `run_skill_script` for skill scripts, limits on the node; a live eval of code mode vs tool calls on target local models | Research question answered in fewer model steps; trace shows one `run_code` doing parallel searches |
| 4 | 012 | **Tool — MCP Server(s)**: the layered trust model (§4.1): user `mcp.json`, free toggles, hash-pinned approve-on-first-use for workflow-carried servers, headless fail-closed; with a `skills` output (`skill://` resources) | Agent uses a third-party MCP server's tools and skills alongside the built-ins |
| 5 | 012 | Structured output + image input on `Agent` (`format` on the native model; reuse dynamic sockets) | Vision agent returns typed fields into FormatString |
| 6 | later | Converge `ChatCompletion` onto `agent_model()` (no tools), retiring ADR-009's duplication, only once parity is proven | Same workflow, one code path |

**Future** (into `Work/planning/future-features.md` once agreed): sub-agents as tools (Agent output →
`LLM_TOOLS`), streaming tokens to the UI, persistent agent memory, cloud providers
(OpenAI/Anthropic) as additional `LLM_CLIENT`s, where native web search and MCP *would* apply.

## 8. Release and distribution (maintainer concern, 2026-11-12)

**The problem today:** comfydv has **no releases**.
- There are no git tags, no CI test workflow and no publishing.
- The `0.1.0` CHANGELOG entry was never tagged.
- ComfyUI-Manager installs by **`git-clone` of the default branch**, so every merge to `main` reaches
  users immediately. A clean-break rename (§5), or this PR's dependency upgrade, would hit them on merge.

**Proposed model:** BEACON's `gitflow` release integration (`beacon integration add release`), adapted
for ComfyUI:

| Branch | Who installs it | Publishes | Version |
|---|---|---|---|
| `main` (default branch, protected, PRs from `develop` only) | Everyone: ComfyUI-Manager git-clone, Comfy Registry, `pip install comfydv` | git tag `vX.Y.Z` + GitHub Release + **PyPI** + **Comfy Registry** | `0.2.0`, `0.3.0`, … |
| `develop` (protected, CI-gated; feature PRs target it) | You: `git checkout develop` in your ComfyUI's `custom_nodes/comfydv`, or `pip install --pre comfydv` | git tag + **PyPI pre-release** | `0.2.0.dev1`, `0.2.0.dev2`, … |

- **Dev builds go to real PyPI as pre-releases, not TestPyPI** (a deviation from BEACON's template).
  pip and uv **ignore pre-releases unless asked** (`--pre` or an exact `==0.2.0.dev3`), so users never
  get them by accident. TestPyPI doesn't host our dependencies (pydantic-ai, fastmcp, monty, …), so
  testing from it needs `--extra-index-url https://pypi.org/simple`, which is clumsy and open to
  dependency confusion.
- **Comfy Registry gets stable releases only.** Its docs require a static semver `version` and say
  nothing about pre-releases. It publishes via `Comfy-Org/publish-node-action` on a version change on
  `main`, with a `REGISTRY_ACCESS_TOKEN` secret and `[tool.comfy] PublisherId`.
- **Versioning:**
  - Switch from `hatch-vcs` (dynamic) to a **static `version` in `pyproject.toml`**, bumped by
    python-semantic-release from Conventional Commits, which the `commit-msg` hook already enforces.
    Both the Registry and BEACON's PSR config need the static field.
  - `feat` → minor, `fix`/`perf` → patch. While at 0.x, `BREAKING CHANGE` → minor (`major_on_zero = false`).
    The rename therefore ships as `0.3.0` (say) with a **Breaking** changelog section, not silently.
  - Decide separately whether the agent release is the moment for `1.0.0`.
- **CI gate** (`ci.yml`, new) on every PR to `develop` and `main`: `ruff check`, `ruff format --check`,
  `ty check`, `pytest -m "not integration and not system"`. Prerequisite: clear the existing broken
  windows on `main` (57 ruff findings, 38 ty diagnostics), or the gate starts red.
- **Bootstrap:** tag the current `main` as `v0.1.0`, so the existing `[Unreleased]` changelog becomes the first PSR release.
- **One-time setup only the maintainer can do:**
  - PyPI pending Trusted Publisher (`release.yml`, environment `pypi`)
  - a Comfy Registry publisher and the `REGISTRY_ACCESS_TOKEN` repo secret
  - GitHub environment `pypi`
  - branch protection for `main` and `develop`
  - confirm `main` stays the default branch

**Effect on in-flight work:** PR #37 (dependency upgrade + telemetry) should merge into `develop`, not
`main`, so it reaches git-clone users only in a release. That needs `develop` created from `main` first.

## 9. Open decisions for the maintainer

Resolved (2026-11-12):

- ✅ **MCP is mandatory.** It is a core dependency, not an extra, and comfydv will grow its own servers. §3.2 follows from this: MCP is the single tool mechanism, and built-ins are in-process FastMCP servers.
- ✅ **Search backend: SearXNG.** DuckDuckGo is dropped from v1.
- ✅ **Upgrade dependencies as needed** (maintainer, 2026-11-12). Done on this branch: `pydantic-ai-slim[openai,mcp]==2.68.0`, `pydantic-ai-harness[codemode]==0.68.0`, `pydantic>=2.12`. The exact-pin trade-off is accepted.
- ✅ **Sandbox: Monty** (§3.4, ADR-013): it runs code-mode snippets and skill scripts, with no authority beyond wired tools.
- ✅ **Rename: clean break**, documented as a breaking change in a versioned release (§5).
- ✅ **Spec layout:** release pipeline (010) → rename (011) → agent (012) (§7).
- ✅ **Code mode default:** `tool_calls` until a live eval on target local models says otherwise.
- ✅ **Skills are first-class and distinct from tools** (§3.3, ADR-012): tools act, skills instruct. Skills are text-only `SKILL.md` folders, progressively disclosed, with their own socket and node category.

- ✅ **MCP trust model: option B** (§4.1), recorded as ADR-015.
- ✅ **Dev channel: PyPI pre-releases** (§8). `develop` is created from `main`, and PR #37 now targets it.
- ✅ **ComfyUI-Manager channels:** "latest" means the Registry release from `main`. Proposal: set `develop` as the default branch, so that "nightly" means `develop`. Verify this first (see `Roadmap/epics/release-pipeline.md`).
- ✅ **ADR-011 to ADR-013 accepted.**

No decisions are open. The next step is `/speckit-specify` for the release pipeline.
