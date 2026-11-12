# ADR-015: MCP server trust model: layered config, free toggles, approve on first use

## Status

> Accepted

_Date:_ 2026-11-12
_Deciders:_ darth-veitcher

---

## Context

The Agent node connects to MCP servers (ADR-011). A stdio MCP server starts a
program on the user's computer. An HTTP MCP server receives data that the agent
sends. People share ComfyUI workflows as files. Thus a workflow file that defines
an MCP server can start a program, or send data to a server, on the computer of
each user who opens it.

The maintainer wants the pattern that Claude Code uses: safe built-in servers
enabled by default, and local config that extends them or overrides them. The
maintainer also wants users to turn servers on and off from the workflow. The
toggles must be transparent, as rgthree's group bypass toggles are.

## Decision

Use four layers. A later layer overrides an earlier layer. A deny always wins
over an allow.

| Layer | Location | Can it add servers? |
|---|---|---|
| 1. Built-in | `comfydv.mcp`, in-process FastMCP servers | Not applicable |
| 2. User config | `<ComfyUI user dir>/comfydv/mcp.json`, in the `mcpServers` format | Yes: HTTP and stdio |
| 3. Managed config | The path in `COMFYDV_MCP_MANAGED` (optional, later) | No. It can only lock: allow lists, deny lists and `allow_workflow_servers: false` |
| 4. Workflow | Widgets on the MCP Servers node | It can only propose a server. The proposal does nothing until the user approves it |

Apply these rules:

1. **A toggle needs no approval.** A workflow can turn a trusted server on or
   off, and it can remove tools from it. A trusted server is one from layer 1
   or 2, or one that the user approved.
2. **A new server needs approval once.** When a workflow proposes a server,
   ComfyUI shows its exact URL, or its exact command, arguments and the names
   of its environment variables. A stdio server shows the warning "runs a
   program on this computer". The user selects **Approve and save**, **Allow
   this session** or **Deny**.
3. **An approval is pinned to a hash.** comfydv keeps the SHA-256 of the
   approved definition. If the definition changes, the server needs approval
   again.
4. **HTTP servers also need approval.** A prompt-injected agent can send data
   to an HTTP server.
5. **A run without a browser fails closed.** An API run (`/prompt`) that refers
   to an unapproved server stops before the first model call. The error names
   the server and tells the user how to approve it.
6. **A workflow never contains secrets.** Config values can refer to
   `${ENV_VAR}`. A workflow definition can name a variable, but it cannot
   contain its value. An export removes header and environment values.
7. **A node can only remove tools.** Config can list allowed and denied tools
   for each server. The node's `allowed_tools` widget can only make that list
   smaller.

The MCP Servers node shows one chip for each server. The chip shows:

- the source: `built-in`, `user`, `approved` or `pending`
- the transport: ⚡ in-process, 🌐 HTTP or 🖥️ local program
- an on/off toggle

A pending chip is red and has a **Review** button. The Agent's `trace` output
starts with a list of the servers and tools that the run could use.

## Consequences

**Easier:**
- A user can share a workflow that needs a server. The person who opens it
  approves that server one time.
- A user can see each server and its source on the canvas.
- A workflow can never start a program, or connect to a server, without the
  user's approval.

**Harder / constrained:**
- comfydv must keep a local approval store and calculate a hash of each definition.
- The approval dialog needs frontend code, and that code needs tests.
- A headless user must add servers to `mcp.json` by hand.

**Debt introduced:**
- The managed config layer (3) is designed but not built yet.

## Considered Alternatives

### Alternative A: Config file only

A workflow can only name a server from `mcp.json`.

**Why rejected:** To share a workflow, each user must edit `mcp.json` by hand.
That is too much work for the people who share workflows.

### Alternative B: Trust HTTP servers from the workflow, and approve only stdio

**Why rejected:** A prompt-injected agent can send data to an HTTP server that the
workflow selects.

---

## Links

- Analysis: `project-management/Work/analysis/llm-agent-harness.md` §4.1
- Related ADRs: [ADR-011](ADR-011-pydantic-ai-agent-harness-with-native-ollama-model.md), [ADR-014](ADR-014-telemetry-off-by-default.md)
