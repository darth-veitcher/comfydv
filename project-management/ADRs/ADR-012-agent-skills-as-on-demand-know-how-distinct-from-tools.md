# ADR-012: Agent skills as on-demand know-how, distinct from tools

## Status

> Accepted

_Date:_ 2026-11-12
_Deciders:_ darth-veitcher

---

## Context

ADR-011 gives comfydv's `Agent` node **tools**: MCP-served actions such as `web_search`, `web_fetch`
and third-party servers. The maintainer also wants **skills**, with a clear line between the two.

Without that line, "skill" tends to blur into "a tool", "a longer system prompt" or "a plugin",
and every later feature argues the boundary again. There is also a practical pressure. Local models
often run with 4–16k contexts, so packing every procedure into the system prompt does not scale past
a handful of procedures.

An open format already exists. The **Agent Skills** format is a folder containing a `SKILL.md`
with YAML frontmatter (`name`, `description`), a Markdown body of instructions and optional
supporting files. Claude, Cursor, Codex, VS Code/Copilot, Gemini, Goose and OpenCode all use it.
FastMCP 4.1, which `pydantic-ai-slim[mcp]` already pulls in (ADR-011), ships a `SkillsProvider`
that serves skill folders as `skill://{name}/SKILL.md` MCP resources. pydantic-ai 2.9 has no skills
feature of its own. Its `AbstractCapability` can contribute instructions (`get_instructions`) and a
toolset (`get_toolset`), and that is all a skills mechanism needs.

## Decision

1. **Definitions.**
   - A **tool** is an *action*: a typed function, executed on an MCP server, that may have side
     effects and returns data.
   - A **skill** is *know-how*: instructions and reference material written for the model, plus
     optional Python scripts. A skill **never acts by itself**: its scripts run only in the Monty
     sandbox (ADR-013), whose only route to the world is the agent's wired tools.
   - A skill may **declare** the tools it expects (`requires-tools` in frontmatter). It never
     **contains** a tool.

   Rule of thumb: *if it does something, it's a tool; if it tells the model how to do something,
   it's a skill.*
2. **Format: Agent Skills `SKILL.md` folders.** We do not invent our own format. Existing
   skills from other ecosystems work unchanged.
3. **Progressive disclosure via a `Skills` capability.**
   - The agent's instructions contain only a catalog: one line per skill, its name and description.
   - Two internal tools let the model pull content on demand. `load_skill(name)` returns the body.
     `read_skill_file(name, path)` returns a supporting file, resolved strictly inside the skill
     folder.
   - These two tools are skill-system plumbing. They never appear on the `LLM_TOOLS` socket, and
     the trace labels them separately (`📘 loaded skill` vs `🔧 tool call`).
   - A per-skill `mode: always` inlines the body instead. This is the escape hatch for models whose
     tool calling is too weak to call `load_skill` reliably.
4. **Separate graph vocabulary.** Skills travel on their own `LLM_SKILLS` socket and live in the
   `dv/llm/skills` category, so tools and skills never share a socket. There are three source nodes:
   - **Skill — Library:** names a skill from configured local skill roots. A workflow can name a
     skill but cannot supply a path.
   - **Skill — Inline:** a skill authored on the node itself.
   - **Skill — from MCP:** reads `skill://` resources, exposed as a second `skills` output on
     **Tool — MCP Server**.
5. **Fail fast on missing prerequisites.** If a wired skill's `requires-tools` names a tool that no
   wired toolset provides, the Agent node raises before the first model call.
6. **Skill scripts run only in the Monty sandbox** (see [ADR-013](ADR-013-monty-sandbox-code-mode-and-skill-scripts.md),
   which amends this ADR's first draft). `scripts/*.py` run through an internal `run_skill_script`
   tool. The skill folder is mounted read-only, and the only way out of the sandbox is the agent's
   wired tools. Code composes tools; it never acts by itself, so the tool/skill delineation holds.
   Non-Python scripts are never run.

## Consequences

**Easier:**
- One unambiguous boundary for future features. New ability → MCP tool. New procedure → skill.
- A graph can offer many skills at the cost of one catalog line each, which matters on small local contexts.
- comfydv's own MCP servers can ship the tools and the skills that teach them together, for
  example `comfydv.mcp.web` plus a built-in `web-research` skill.
- Skills written for Claude Code or Cursor can be reused in ComfyUI as they are.

**Harder / constrained:**
- Progressive disclosure depends on the model choosing to call `load_skill`. Weak models need `mode: always`.
- Skills are trusted instructions. A malicious skill is a prompt injection. Mitigations: skill roots
  are local and user-controlled; MCP-served skills carry their server's trust; scripts run only inside
  Monty and can act only through wired tools (ADR-013).
- `requires-tools` is our own frontmatter key, not part of the shared format. Other ecosystems ignore it harmlessly.

**Debt introduced:**
- Third-party skills whose scripts need full CPython (third-party packages, unsupported syntax) are
  only partially usable: their instructions load, but their scripts fail Monty's checks with a clear error.

## Considered Alternatives

### Alternative A: Skills as tools (each skill becomes a callable tool returning its text)

**Why rejected:** It erases the delineation the maintainer asked for. Skills would inflate the tool
schema list every step, and in traces and UI they'd look identical to actions.

### Alternative B: Skills as system-prompt fragments (concatenate selected skills)

**Why rejected:** It is always-on context cost with no progressive disclosure, so it doesn't scale on
small local contexts. It is kept as the per-skill `mode: always` escape hatch, not as the default.

### Alternative C: A comfydv-specific skill format (for example a JSON widget schema)

**Why rejected:** It cuts us off from an existing, multi-vendor ecosystem for no gain.
FastMCP already speaks `SKILL.md`.

### Alternative D: Never execute skill scripts

**Originally chosen, then superseded by ADR-013.** The original reason ("needs a code-execution tool
with real sandboxing inside ComfyUI's process space") is answered by Monty: a language-level Python
sandbox, run in a worker subprocess, with no host access by default.

---

## Links

- Analysis: `project-management/Work/analysis/llm-agent-harness.md` §3.3
- Related ADRs: [ADR-013](ADR-013-monty-sandbox-code-mode-and-skill-scripts.md) (script execution), [ADR-011](ADR-011-pydantic-ai-agent-harness-with-native-ollama-model.md)
- External reference: Agent Skills format (agentskills.io); FastMCP `fastmcp.server.providers.skills`
