# ADR-013: Monty sandbox for code mode and skill scripts, with no authority of its own

## Status

> Accepted

_Date:_ 2026-11-12
_Deciders:_ darth-veitcher

---

## Context

ADR-012's first draft rejected running skill scripts, on the grounds that safe execution would
need "a code-execution tool with real sandboxing inside ComfyUI's process space". The maintainer
pointed at **Monty** (`pydantic-monty`, Pydantic's Rust-implemented Python sandbox for AI-written
code), which removes most of that objection. Verified on 2026-11-12:

- **Packaging:** `pydantic-monty` 1.6.0 (MIT) ships wheels for Windows (win_amd64, win32), macOS
  (x86_64, arm64) and Linux (manylinux and musllinux, several arches). It needs Python ≥3.10 and
  no Docker or VM.
- **Security model** (from the docs, and probed live; see Evidence): a *language-level* sandbox. There is
  no filesystem, network or environment access unless the host grants it. Host functions are passed
  in explicitly. Execution runs in a `monty` worker subprocess, so an interpreter crash can't take
  down ComfyUI. There are memory and time limits, and execution can be paused and resumed.
- **Language subset:** CPython-3.14 semantics where implemented, a partial stdlib (json, re,
  datetime, math, collections, asyncio.gather/run/sleep, …), and **no third-party packages**.
  Not supported: class inheritance, generators, `del`, method decorators, user-defined exceptions.
- **pydantic-ai integration:** `pydantic-ai-harness[codemode]` provides a `CodeMode` capability. The
  model gets one `run_code` tool and writes Python that calls the agent's other tools as async
  functions, so several tool calls (parallel via `asyncio.gather`) happen in **one model step**.
  The snippet is type-checked against generated tool stubs before it runs.

### Evidence (scratch venv, pydantic-ai-slim 2.68.0 + pydantic-ai-harness 0.68.0 + pydantic-monty 1.6.0)

A `FunctionModel` emitted one `run_code` call whose snippet called a host tool twice through
`asyncio.gather` and then probed the host. Results:

- The tools returned `[3, 2]` in a single model step (2 model requests in total, including the final answer).
- `open("/etc/passwd")` raised `PermissionError`.
- `os.environ` raised `RuntimeError: 'os.environ' is not supported in this environment`.
- `import socket` was rejected by the pre-execution type check (`unresolved-import`) before anything ran.

### Version constraint discovered

`pydantic-ai-harness` 0.68.0 pins **`pydantic-ai-slim==2.68.0` exactly**, and harness versions move in
lockstep with pydantic-ai. comfydv is on 2.9.0, and against that the resolver can only pick an
obsolete harness (0.8.0). Adopting `CodeMode` therefore means **upgrading pydantic-ai 2.9 → 2.68**
and pinning it exactly. pydantic-ai 2.68 also prints a first-run banner to stdout unless
`pydantic_ai.BANNER_ENABLED = False` or `PYDANTIC_AI_NO_BANNER` is set. comfydv handles this, along with the
other telemetry defaults, in [ADR-014](ADR-014-telemetry-off-by-default.md). 2.68's `OllamaModel` is still OpenAI-compatible (`/v1`), so ADR-011's native Ollama model
is still required.

## Decision

1. **Monty is the single sandbox.** It is used for two things:
   - **Code mode:** an Agent-level `execution` choice, `tool_calls` (default) or `code_mode`, using
     `pydantic_ai_harness.CodeMode`.
   - **Skill scripts:** `*.py` files under a skill's `scripts/` folder become runnable through an internal
     `run_skill_script(skill, script, args)` tool, executed in Monty. The skill folder is mounted
     **read-only** (`MountDir(..., mode="read-only")`).
2. **The sandbox has no authority of its own.** Its only route to the outside world is the
   agent's wired **tools**, exposed as external functions. There is no network, no host filesystem
   beyond the read-only skill mount, and no environment. This keeps the delineation of ADR-012:
   tools are still the only things that act. Code, whether the model wrote it or a skill shipped it,
   only *composes* tool calls.
3. **Conservative limits by default:** 30 s per snippet or script, 256 MiB memory, and a tool-call cap
   per snippet (harness default 100; comfydv default lower). They are exposed as Agent node inputs.
4. **Honest about the subset.**
   - A skill script that uses unsupported features (third-party imports, classes with inheritance, …)
     fails the type check or parse, and the model gets a clear error naming the script.
   - Non-Python scripts (`.sh`, …) are never run.
   - The README states that most third-party skill scripts written for full CPython will not run.
     Skills authored for comfydv should target Monty's subset.
5. **Upgrade pydantic-ai to 2.68 and pin exactly** (`pydantic-ai-slim[openai,mcp]==2.68.0`,
   `pydantic-ai-harness[codemode]==0.68.0`) in `pyproject.toml` and `requirements.txt`. This is a
   prerequisite step with regression tests over the existing llama.cpp structured-output path (`_llm/chat.py`).
   The maintainer approved upgrading as needed (2026-11-12); the upgrade landed with this ADR's PR,
   along with the raised `pydantic>=2.12` floor that pydantic-ai 2.68 requires.

## Consequences

**Easier:**
- Multi-step tasks need fewer LLM round trips. A local model that takes tens of seconds per step can
  fan out search, fetch and others in one snippet. This is the biggest latency win available for slow local models.
- Skills can carry real procedures: parsing, transforming, deterministic calculation. The model
  doesn't have to do arithmetic or string-munging in its head.
- No container runtime required, with the same behaviour on Windows, macOS and Linux.

**Harder / constrained:**
- **Language-level, not OS-level, isolation.** Monty has no seccomp or VM. A Monty bug is a sandbox
  escape into the ComfyUI user's account. Mitigation: pin, track Monty security advisories (it runs a
  bounty program), and keep tools (the host functions) as narrow as ever. A tool is full host authority.
- **Exact pydantic-ai pin.** Every harness upgrade forces a pydantic-ai upgrade. If another
  ComfyUI node pack pins a different pydantic-ai, they can't coexist.
  - Escape hatch: drop `pydantic-ai-harness` and drive `pydantic-monty` directly behind our own
    small capability. Monty itself has a loose `>=1.5,<2` range.
- `pydantic-ai-harness` is 0.x ("API may change between minor releases").
- Code mode asks small local models to write correct Python in a subset. Quality is unproven, which
  is why `tool_calls` stays the default until a live evaluation on target models says otherwise.
- Footprint: the `[mcp]` + `[codemode]` stack measured 142 MB across 67 packages, against 90 MB / 62
  packages for `[mcp]` alone. `codemode` also pulls `pydantic-ai-slim[duckduckgo]` transitively, but
  comfydv doesn't use it.

**Debt introduced:**
- Third-party skills whose scripts need CPython packages remain instruction-only.

## Considered Alternatives

### Alternative A: Never execute anything (ADR-012's original stance)

**Why rejected:** Monty removes the main reason (no viable in-process sandbox). Refusing code
execution would also give up code mode's round-trip savings, which matter most on slow local models.

### Alternative B: Container sandbox (Docker or similar) per execution

**Why rejected:** It needs a container runtime on every ComfyUI host (many are Windows desktops),
adds seconds of startup per run and runs full CPython. Its stronger OS-level isolation doesn't justify
the cost for code whose only side effects go through our tools anyway.

### Alternative C: IPython Code Mode (full CPython kernel)

**Why rejected:** Its own docs say not to run it without a sandbox. It is full host authority, and
exactly the risk this ADR avoids.

### Alternative D: `pydantic-monty` directly, without `pydantic-ai-harness`

**Why not chosen (kept as escape hatch):** It avoids the exact pydantic-ai pin, but we'd have to
re-implement the tool stubs, type-checking, error formatting and REPL state that `CodeMode` already
provides. Revisit if the lockstep pin causes real conflicts.

---

## Links

- Analysis: `project-management/Work/analysis/llm-agent-harness.md` §3.4
- Related ADRs: [ADR-001](ADR-001-stdlib-logging-over-console-libraries.md) (banner), [ADR-011](ADR-011-pydantic-ai-agent-harness-with-native-ollama-model.md), [ADR-012](ADR-012-agent-skills-as-on-demand-know-how-distinct-from-tools.md) (amends its "no script execution" decision)
- External reference: https://pydantic.dev/docs/monty/get-started/ ; https://pydantic.dev/docs/ai/harness/code-mode/
