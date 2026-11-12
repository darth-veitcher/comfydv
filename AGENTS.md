# AGENTS.md

## What this repository is

comfydv is a ComfyUI node pack: utility nodes (Format String, Random Choice,
Circuit Breaker) and local LLM nodes for Ollama and llama.cpp. ComfyUI loads it
from `custom_nodes/`. The repository root `__init__.py` is the ComfyUI entry
point, and it re-exports `src/comfydv/__init__.py`.

## Commands

Set up:

```bash
uv sync                    # runtime and dev dependencies, with pinned ruff and ty
uv sync --group docs       # add the MkDocs toolchain
```

Run the quality gates. All four must pass before work is done ([constitution, Quality Gates](.specify/memory/constitution.md)). The integration and system tests skip when their service is not running:

```bash
uv run ruff check --fix && uv run ruff format
uv run ty check
uv run pytest
beacon doctor --strict
```

The test tiers are pytest markers:

| Tier | Command | Needs |
|---|---|---|
| Unit | `uv run pytest -m "not integration and not system"` | Nothing |
| Integration (`integration`) | `just test-integration` | Ollama at `localhost:11434` |
| System (`system`) | `just test-system` | The Docker Compose harness (`just up-d`) |

Other commands:

- Build the docs site: `uv run mkdocs build --strict`.
- Check the documentation: `beacon docs check`.
- Release: `/git:release` opens a PR from `develop` to `main`. A release pipeline is planned. Until then, no package publishes. Only the docs site deploys from `main` (`.github/workflows/docs.yml`).

## Rules

- Each node keeps ComfyUI's registration contract ([constitution I](.specify/memory/constitution.md)).
- Run user templates only in the Jinja2 sandbox. Never call `eval()` or `exec()` on user text ([constitution II](.specify/memory/constitution.md)).
- Write the test first, and do not commit a failing test ([constitution III](.specify/memory/constitution.md)).
- Guard each `comfy`, `server` and `folder_paths` import. The tests run without ComfyUI ([constitution III and IV](.specify/memory/constitution.md)).
- Do not move an existing output socket. Saved workflows connect by position ([constitution VI](.specify/memory/constitution.md)).
- Use Conventional Commits. The `commit-msg` hook enforces them. Do not bypass it ([.claude/CLAUDE.md](.claude/CLAUDE.md)).
- Cut branches from `develop`, and open PRs to `develop`. Only a release PR goes to `main` ([.claude/CLAUDE.md](.claude/CLAUDE.md)).
- Write documentation and artefacts to [docs/WRITING.md](docs/WRITING.md). Use the `beacon-docs` skill.
- Do not edit `.claude/CLAUDE.md` or `docs/WRITING.md`. BEACON owns them ([docs/WRITING.md, section 1](docs/WRITING.md)).
- Never add code that sends telemetry. Add each new off-switch to `src/comfydv/_llm/_telemetry.py` ([ADR-014](project-management/ADRs/ADR-014-telemetry-off-by-default.md)).

## Where things are

| Path | Contents |
|---|---|
| `src/comfydv/` | Node classes and `NODE_CLASS_MAPPINGS` |
| `src/comfydv/_llm/` | The `LLMProvider` interface and the Ollama and llama.cpp providers. No ComfyUI imports. |
| `src/js/` | ComfyUI frontend extensions |
| `tests/` | pytest suite. `conftest.py` mocks the ComfyUI modules. |
| `workflows/` | Example ComfyUI workflows |
| `docs/` | MkDocs source. `scripts/gen_ref_pages.py` makes the home page from `README.md`. |
| `specs/` | Spec Kit specs, plans and tasks |
| `project-management/ADRs/` | Architecture decisions |
| `project-management/Roadmap/` | Strategy and epics |
| `docker/`, `docker-compose*.yml`, `Justfile` | The ComfyUI dev and test harness |

## Current work

- Strategy and order of work: [project-management/Roadmap/README.md](project-management/Roadmap/README.md).
- Active spec: [specs/010-release-pipeline/spec.md](specs/010-release-pipeline/spec.md), in the release pipeline epic ([project-management/Roadmap/epics/release-pipeline.md](project-management/Roadmap/epics/release-pipeline.md)). It has no plan yet. The next step is `/speckit-plan`.
- Agent harness design: [project-management/Work/analysis/llm-agent-harness.md](project-management/Work/analysis/llm-agent-harness.md).

## Known problems

- **Importing `comfydv` tries to reach Ollama.** The package populates the model dropdowns at import time. Without a server, it logs a warning and continues. This is not an error.
- **Ollama's OpenAI-compatible endpoint resets `num_ctx` on each request.** Use the native `/api/chat` endpoint for Ollama (ADR-009, ADR-011).
- **The sampling option nodes have no effect on llama.cpp.** llama-server ignores the nested `options` object. Set the values as `llama-server` start options. The Seed node has an effect only on retries.
- **pydantic-ai has an exact pin.** `pydantic-ai-harness` requires the exact pydantic-ai version, so upgrade both together (ADR-013).
- **ty cannot read the signature of `pytest.skip`.** The `ty: ignore` comments in `tests/conftest.py` are correct.
