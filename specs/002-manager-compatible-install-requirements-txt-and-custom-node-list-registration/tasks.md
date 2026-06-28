# Tasks: Manager-Compatible Install

**Input**: Design documents from `specs/002-manager-compatible-install-requirements-txt-and-custom-node-list-registration/`

**Branch**: `002-manager-install`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[US#]**: User story label from spec.md
- **-T / -I suffix**: TDD pair — `-T` (write failing test) committed alone before its `-I` (implementation)

---

## Phase 1: Setup

**Purpose**: Scaffold the test file and BDD feature files before any implementation.

- [ ] T001 Create `tests/test_packaging.py` with the module skeleton (imports, helpers) and one `pass` placeholder per test function — no assertions yet
- [ ] T002 Create BDD feature files in `specs/002-manager-compatible-install-requirements-txt-and-custom-node-list-registration/features/` (one per US) from the Gherkin scenarios in spec.md

---

## Phase 2: User Story 1 — Clean dependency install (Priority: P1)

**Goal**: `pip install -r requirements.txt` exits 0 and makes `import jinja2` succeed.

**Independent Test**: `uv run pytest tests/test_packaging.py::TestRequirementsTxt` — all pass in a clean environment.

### User Story 1 — TDD pairs

- [ ] T010-T [US1] Write FAILING test in `tests/test_packaging.py` asserting `requirements.txt` exists, contains `jinja2>=3.1.6`, does not contain `colorama`/`termcolor`/`rich`/`.`, and every package listed is present in `pyproject.toml [project.dependencies]` (red)
- [ ] T010-I [US1] Replace `requirements.txt` with hand-authored content: header comment explaining authoring policy + `jinja2>=3.1.6` so T010-T passes (green)
- [ ] T011-T [US1] Write FAILING test in `tests/test_packaging.py` asserting `aiohttp` appears in `pyproject.toml [project.dependencies]` (not only in `[dependency-groups]`) (red)
- [ ] T011-I [US1] Move `aiohttp>=3.9.0` from `[dependency-groups] dev` to `[project.dependencies]` in `pyproject.toml`; run `uv sync` so T011-T passes (green)

**Checkpoint**: `uv run pytest tests/test_packaging.py::TestRequirementsTxt` green.

---

## Phase 3: User Story 2 — ComfyUI Manager registration (Priority: P1)

**Goal**: comfydv appears in Manager's search UI and installs in one click.

**Independent Test**: `comfy-manager-entry.json` exists, is valid JSON, and passes schema assertions in `tests/test_packaging.py::TestManagerEntry`.

**Note**: The actual Manager UI test (searching and clicking Install) is a manual step performed after the `ltdrdata/ComfyUI-Manager` PR is merged. T020-T/T020-I cover the automatable prerequisite: the draft entry JSON is correct.

### User Story 2 — TDD pairs

- [ ] T020-T [US2] Write FAILING test in `tests/test_packaging.py` asserting `comfy-manager-entry.json` at the repo root does not exist yet (or has wrong/missing fields) — this will go GREEN once T020-I creates it correctly (red)
- [ ] T020-I [US2] Create `comfy-manager-entry.json` at the repo root with the correct Manager schema: `author`, `title`, `reference`, `files`, `install_type: "git-clone"`, `description`, `nodename` list matching `NODE_CLASS_MAPPINGS` display names — so T020-T passes (green)

**Manual step** (not a task pair — requires human action after merge):
- Submit a PR to `ltdrdata/ComfyUI-Manager` adding the `comfy-manager-entry.json` content to `custom-node-list.json`. Reference the live `main` branch; confirm `requirements.txt` fix is on `main` first.

**Checkpoint**: `uv run pytest tests/test_packaging.py::TestManagerEntry` green.

---

## Phase 4: User Story 3 — Accurate package metadata (Priority: P2)

**Goal**: `@description` in root `__init__.py` names only the three existing nodes.

**Independent Test**: `uv run pytest tests/test_packaging.py::TestMetadata` — `@description` contains no mention of non-existent nodes.

### User Story 3 — TDD pairs

- [ ] T030-T [US3] Write FAILING test in `tests/test_packaging.py` asserting that the `@description` field in `__init__.py` does not contain the strings `"model memory"`, `"Model Unloader"`, or any other reference to non-existent nodes (red)
- [ ] T030-I [US3] Update `@description` in root `__init__.py` to: `"Quality of life ComfyUI nodes: dynamic string formatting with Python f-strings or Jinja2 templates, seed-controlled random input selection, and workflow circuit-breaker for conditional queue interruption."` so T030-T passes (green)

**Checkpoint**: `uv run pytest tests/test_packaging.py::TestMetadata` green.

---

## Phase 5: User Story 4 — Docker Compose local test harness (Priority: P2)

**Goal**: `docker compose up --build` starts a CPU-only ComfyUI with comfydv loaded; all three nodes appear in startup logs.

**Independent Test**: `uv run pytest tests/test_packaging.py::TestDockerCompose` — `docker-compose.yml` exists, is valid YAML, and declares a `comfyui` service.

### User Story 4 — TDD pairs

- [ ] T040-T [US4] Write FAILING test in `tests/test_packaging.py` asserting `docker-compose.yml` exists at the repo root and has a `comfyui` service with a `ports` mapping including `8188` (red)
- [ ] T040-I [US4] Create `docker-compose.yml` at the repo root: single `comfyui` service, `python:3.11-slim` base, installs ComfyUI CPU-only (`torch` CPU wheel), symlinks `comfydv` into `custom_nodes/`, runs `pip install -r requirements.txt`, starts `python main.py --cpu --listen 0.0.0.0`, exposes port 8188; create accompanying `docker/Dockerfile` so T040-T passes (green)
- [ ] T041-T [US4] Write test asserting `docker/Dockerfile` exists and `FROM python:3.11` is the base (so we can verify the GPU-free constraint in CI) (red)
- [ ] T041-I [US4] Create `docker/Dockerfile` with CPU-only ComfyUI install so T041-T passes (green)

**Checkpoint**: `uv run pytest tests/test_packaging.py::TestDockerCompose` green. Manual smoke: `docker compose up --build` and inspect logs for `"Loaded custom nodes from comfydv"`.

---

## Phase 6: Polish & Quality Gates

- [ ] T050 Run `uv run ruff check --fix && uv run ruff format` on `tests/test_packaging.py` and confirm clean
- [ ] T051 Run `uv run pytest` and confirm all tests pass (existing 11 + new packaging tests)
- [ ] T052 Run `beacon doctor --strict` and confirm 0 failures

---

## Dependencies & Execution Order

- **Phase 1 (T001–T002)**: No dependencies — start here; creates test scaffold
- **Phase 2 (US1)**: Requires Phase 1; T010-T before T010-I, T011-T before T011-I; can run with Phase 2 in parallel across files
- **Phase 3 (US2)**: Requires Phase 1; T020-T before T020-I; independent of Phase 2 (different files)
- **Phase 4 (US3)**: Requires Phase 1; T030-T before T030-I; independent of Phases 2–3
- **Phase 5 (US4)**: Requires Phase 1; T040-T before T040-I, T041-T before T041-I; independent of Phases 2–4
- **Phase 6 (Polish)**: Requires all prior phases complete; tasks are sequential

### TDD rule (enforced by `beacon doctor --strict`)

Every `-T` task is committed alone (failing) before its `-I` partner. Never combine a `-T` and its `-I` in the same commit.

---

## Implementation Strategy

### MVP (Phases 1–3 only)

1. T001–T002 (scaffold)
2. T010-T → T010-I → T011-T → T011-I (fix requirements.txt + pyproject.toml)
3. T020-T → T020-I (draft Manager entry JSON)
4. Submit Manager PR manually

This alone unblocks ComfyUI Manager installation. Users can find and install the package, and deps install correctly.

### Full delivery

Continue Phase 4 (metadata) → Phase 5 (Docker harness) → Phase 6 (quality gates). The Docker harness is valuable but not blocking for the Manager submission.
