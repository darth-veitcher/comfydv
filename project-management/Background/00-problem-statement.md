# Problem Statement

<!--
BEACON SEED phase deliverable. Update this as requirements evolve — it is a living document.
Record the date and reason whenever you change it.
-->

## Core Problem

ComfyUI ships no general-purpose string formatting, random-selection, or workflow-interruption primitives, forcing workflow creators to work around missing utilities with brittle workarounds or custom Python script nodes that can't be shared easily.

## Target User

**Who:** ComfyUI power users building automated or parameterised image/video generation pipelines  
**Context:** Mid-workflow, when they need to compose prompts from variables, randomly sample a style or subject, or halt a misbehaving pipeline without killing the ComfyUI process  
**Current pain:** They either hard-code values in prompt strings, rely on community nodes with inconsistent APIs, or paste raw Python into script nodes — none of which is reusable, version-controlled, or easy to chain

## Success Criteria

How will we know this is working? Make these measurable.

- [x] `FormatString` node accepts an arbitrary template (Python f-string or Jinja2) and dynamically exposes detected variables as typed inputs, with pass-through outputs for downstream chaining
- [x] `RandomChoice` node accepts an arbitrary number of typed inputs and returns one at random with reproducible seed control
- [x] `CircuitBreaker` node raises `InterruptProcessingException` to halt a run without crashing ComfyUI when `status=False`
- [ ] All nodes install via the standard ComfyUI custom-node mechanism (drop into `custom_nodes/`, restart server)
- [ ] Node tests pass outside ComfyUI (no ComfyUI import required in the test suite)
- [ ] `ruff`, `ty`, and `beacon doctor` are all clean before any PR merges

## Non-Goals

Explicitly naming what we are **not** solving prevents scope creep.

1. NOT a general-purpose Python scripting node — template execution is sandboxed; arbitrary code is not supported
2. NOT a ComfyUI Manager listing or PyPI release at this stage — distribution is manual install or git clone
3. NOT cross-platform GPU tooling — nodes are CPU-only utilities; the ComfyUI host handles GPU concerns
4. NOT a replacement for ComfyUI's native primitive nodes — these nodes fill the gaps, not the core

## Why This Matters

ComfyUI workflows are increasingly used for production pipelines — batch prompt generation, style randomisation, asset naming — but the node library has always under-served text manipulation. A small, well-tested utility pack that installs in seconds and requires zero Python knowledge from the end user removes a class of frustrating workarounds and lets workflow creators focus on composition, not plumbing.

## Constraints

- Must load inside ComfyUI's existing import system — top-level `__init__.py` exposes `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`
- Jinja2 rendering **must** use `SandboxedEnvironment` to prevent arbitrary code execution from user-supplied templates
- Tests must not require a live ComfyUI process — `comfy.*` imports are guarded and mocked at test time
- Python ≥ 3.11 (`requires-python` in `pyproject.toml`); managed with `uv`

---

_Created:_ 2026-06-28  
_Last updated:_ 2026-06-28 — initial SEED artefact  
_Status:_ Living document — update when requirements evolve
