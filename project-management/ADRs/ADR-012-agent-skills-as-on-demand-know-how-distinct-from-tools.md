# ADR-012: Agent skills as on-demand know-how, distinct from tools

## Status

> Accepted

Amended 2026-11-12, before merge: use `pydantic_ai_harness.Skills` for the catalog and the load step.

_Date:_ 2026-11-12
_Deciders:_ darth-veitcher

---

## Context

ADR-011 gives comfydv's `Agent` node **tools**: MCP-served actions such as `web_search`, `web_fetch`
and third-party servers. The maintainer also wants **skills**, with a clear line between the two.

Without that line, the meaning of "skill" is not clear. It can mean "a tool", "a longer system
prompt" or "a plugin", and each later feature has the same discussion again. Local models often run
with 4–16k contexts, so a system prompt with all the procedures does not scale past a small number.

These facts apply (verified 2026-11-12, pydantic-ai-slim 2.68.0, pydantic-ai-harness 0.68.0):

- **An open format exists.** An Agent Skills skill is a folder with a `SKILL.md` file. The file
  has YAML frontmatter (`name`, `description`) and a Markdown body of instructions. The folder can
  also have supporting files. Claude, Cursor, Codex, VS Code/Copilot, Gemini, Goose and OpenCode use it.
- **pydantic-ai-harness has a `Skills` capability** (`pydantic_ai_harness.skills`, extra `skills`).
  It puts a catalog of skill names and descriptions in the agent's instructions. The model loads a
  skill with the `load_capability` tool. The capability reads skill folders from a pydantic-ai
  workspace, and it can scan skill files for prompt injection. It does not read supporting files,
  and it does not run scripts.
- **FastMCP 4.1 has a `SkillsProvider`.** It serves skill folders as `skill://{name}/SKILL.md` MCP
  resources. It is in the FastMCP `server` extra. `pydantic-ai-slim[mcp]` installs only the
  `client` extra, so `import fastmcp.server.providers.skills` fails in the current environment.

## Decision

Give the agent skills as Agent Skills `SKILL.md` folders that the model reads on demand, on a
socket that is separate from tools.

1. **Definitions.**
   - A **tool** is an *action*: a typed function that runs on an MCP server. It can have side
     effects, and it returns data.
   - A **skill** is *know-how*: instructions and reference material for the model, and optional
     Python scripts. A skill **never acts by itself**. Its scripts run only in the Monty sandbox
     (ADR-013), and the sandbox can reach the world only through the agent's wired tools.
   - A skill can **declare** the tools that it expects (`requires-tools` in the frontmatter). It
     never **contains** a tool.

   Rule of thumb: *if it does something, it is a tool. If it tells the model how to do something,
   it is a skill.*
2. **Format: Agent Skills `SKILL.md` folders.** We do not make a format of our own. Skills from
   other tools operate without change.
3. **Use `pydantic_ai_harness.Skills` for the catalog and the load step.** comfydv adds only what
   the harness does not do:
   - `read_skill_file(name, path)` gives a supporting file. comfydv resolves the path strictly
     inside the skill folder.
   - `run_skill_script` runs a script in Monty (item 6).
   - Inline skills and MCP-served skills (item 4). comfydv gives them to the harness as skill
     folders in the run's workspace.
   - A per-skill `mode: always` puts the body in the instructions. This is the escape hatch for a
     model that cannot call the load tool reliably.

   These internal tools never appear on the `LLM_TOOLS` socket. The trace shows them separately
   (`📘 loaded skill` and `🔧 tool call`).
4. **Separate graph vocabulary.** Skills go on their own `LLM_SKILLS` socket, in the
   `dv/llm/skills` category. Tools and skills never share a socket. There are three source nodes:
   - **Skill — Library** names a skill from the configured local skill roots. A workflow can name
     a skill, but it cannot give a path.
   - **Skill — Inline** holds a skill that the user writes on the node.
   - **Skill — from MCP** reads `skill://` resources. It is a second `skills` output on
     **Tool — MCP Server**.
5. **Fail before the first model call when a tool is missing.** If the `requires-tools` of a wired
   skill names a tool that no wired toolset gives, the Agent node raises an error.
6. **Skill scripts run only in the Monty sandbox** ([ADR-013](ADR-013-monty-sandbox-code-mode-and-skill-scripts.md)
   amends the first draft of this ADR). The internal `run_skill_script` tool runs `scripts/*.py`.
   Monty mounts the skill folder read-only, and the agent's wired tools are the only way out of
   the sandbox. Code composes tools and never acts by itself, so the line between tools and skills
   stays. comfydv never runs a script that is not Python.

## Consequences

**Easier:**
- Each later feature has one clear boundary. A new ability is an MCP tool. A new procedure is a skill.
- A graph can offer many skills for one catalog line each. This is important for small local contexts.
- comfydv does not keep its own catalog and load code, because the harness gives it.
- comfydv's own MCP servers can ship the tools and the skills that teach them together, for
  example `comfydv.mcp.web` and a built-in `web-research` skill.
- Skills from Claude Code or Cursor operate in ComfyUI without change.

**Harder / constrained:**
- Progressive disclosure needs the model to call the load tool. A weak model needs `mode: always`.
- Skills are trusted instructions, so a malicious skill is a prompt injection. Mitigations: the
  skill roots are local, and the user controls them. MCP-served skills have the trust of their
  server. Scripts run only in Monty, and they can act only through wired tools (ADR-013). The
  harness scanner can also check skill files.
- `requires-tools` is our own frontmatter key, not part of the shared format. Other tools ignore it.
- The `Skills` capability needs `pydantic-ai-harness[codemode,skills]` in `pyproject.toml` and
  `requirements.txt`. Add the `skills` extra with the first skill work.
- Skill — from MCP needs `fastmcp-slim[server]` (the `SkillsProvider`) when a comfydv MCP server
  serves skills. Add it with that work.
- The harness `Skills` capability is 0.x, so its API can change. The exact pin (ADR-013) controls
  when it changes.

**Debt introduced:**
- Some third-party skills have scripts that need full CPython (third-party packages, syntax that
  Monty does not support). Their instructions load, but their scripts fail Monty's checks with a
  clear error.

## Considered Alternatives

### Alternative A: Skills as tools (each skill is a tool that returns its text)

**Why rejected:** It removes the line that the maintainer asked for. Skills would make the list of
tool schemas longer at each step. In traces and in the UI, they would look the same as actions.

### Alternative B: Skills as parts of the system prompt

**Why rejected:** It costs context at all times, with no progressive disclosure, so it does not
scale on small local contexts. We keep it as the per-skill `mode: always` escape hatch, not as the
default.

### Alternative C: A skill format of our own (for example a JSON widget schema)

**Why rejected:** It cuts us off from an existing multi-vendor ecosystem, for no gain. The harness
and FastMCP already read `SKILL.md`.

### Alternative D: Never run skill scripts

**First chosen, then replaced by ADR-013.** The first reason was "needs a code-execution tool with
real sandboxing inside ComfyUI's process space". Monty answers it: a language-level Python sandbox
in a worker subprocess, with no host access by default.

### Alternative E: Our own `Skills` capability (the first draft of this ADR)

**Why rejected:** `pydantic_ai_harness.Skills` already gives the catalog and the load step, with
the same format and a prompt-injection scanner. Our own copy would repeat it (DRY). comfydv builds
only the parts that the harness does not have.

---

## Links

- Analysis: `project-management/Work/analysis/llm-agent-harness.md` §3.3
- Related ADRs: [ADR-013](ADR-013-monty-sandbox-code-mode-and-skill-scripts.md) (script execution), [ADR-011](ADR-011-pydantic-ai-agent-harness-with-native-ollama-model.md)
- External reference: Agent Skills format (agentskills.io); `pydantic_ai_harness.skills`; FastMCP `fastmcp.server.providers.skills`
