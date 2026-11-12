# Epic: LLM Agent Harness: Tools, Skills, Sandbox

<!-- Write this epic to section 7 of docs/WRITING.md (ASD-STE100). -->

## Status
Planning  — started 2026-11-12

## Why now
The LLM nodes can only chat. The maintainer wants an agent that searches the
web, does tasks in more than one step and uses MCP servers. The dependency
upgrade (pydantic-ai 2.68, MCP, Monty) is complete, so this work can start.

## Specs
_SpecKit specs that contribute to this epic. `beacon specify --epic <slug>`
links them. Otherwise, add each one by hand after you run `/speckit-specify`._

<!-- - specs/012-llm-agent/   — Agent node, native Ollama model, tools, skills, sandbox -->

## ADRs
- [ADR-011](../../ADRs/ADR-011-pydantic-ai-agent-harness-with-native-ollama-model.md) — pydantic-ai Agent with a native Ollama model; MCP is the tool mechanism.
- [ADR-012](../../ADRs/ADR-012-agent-skills-as-on-demand-know-how-distinct-from-tools.md) — skills are separate from tools.
- [ADR-013](../../ADRs/ADR-013-monty-sandbox-code-mode-and-skill-scripts.md) — Monty sandbox for code mode and skill scripts.
- [ADR-014](../../ADRs/ADR-014-telemetry-off-by-default.md) — telemetry off by default.
- [ADR-015](../../ADRs/ADR-015-mcp-server-trust-model.md) — MCP server trust model.

## Success criteria
- An Agent node answers a question with web search and web fetch on a local
  Ollama model. The node shows each step while it runs.
- The same graph operates with llama.cpp when you change only the client node.
- With a skill wired, the agent loads it, and the trace shows the load. A test checks that the
  answer follows a step that only the skill gives.
- Code mode does the same task in fewer model steps than tool calls.
- A workflow cannot start an MCP server or connect to one without the user's approval.
- An API run that refers to an unapproved server fails before the first model call.

## Non-goals
- Code execution outside the Monty sandbox.
- Human approval of each tool call during a run.
- Cloud model providers.

## Notes
Bullet order and detail: `project-management/Work/analysis/llm-agent-harness.md` §7.
Code mode stays off by default until a live test on local models.
