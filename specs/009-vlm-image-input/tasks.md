# Tasks: VLM Image Input for ChatCompletion

**Input**: Design documents from `/specs/009-vlm-image-input/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/image-input-contract.md

**Tests**: First-class — every implementation task has a paired failing-test task (`-T`/`-I` suffix). Contracts T1–T6 in `contracts/image-input-contract.md` map to the pairs below.

**Organization**: Grouped by user story (spec.md priorities: US1 P1 🎯 MVP, US2 P1, US3 P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US3
- **-T / -I**: paired test (red) / implementation (green) — the `-T` is committed failing before its `-I` partner (no test + impl in one commit)

## Path Conventions

Single project: `src/comfydv/`, `tests/` at repo root. Purely additive edits to
the existing `_llm`/node files (plan.md Structure Decision) — no new module.
`src/comfydv/_llm/` stays torch/numpy/Pillow-free (Constitution IV); tensor
handling lives only in the `comfy`-guarded `ollama.py`.

---

## Phase 1: Setup

- [x] T001 Add `pillow` to `[dependency-groups].dev` in `pyproject.toml` — lets the node's tensor→PNG encoder be unit-tested without a live ComfyUI; runtime Pillow/numpy are ComfyUI-provided, so **no core runtime dependency is added** (research.md Decision 4)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the image carrier every path depends on. **⚠️ No user story work can begin until this is complete.**

- [x] T002-T Write FAILING test: `Message.images` defaults to `None`, round-trips a base64 list, and a text-only message's transport dump **omits** the `images` key (byte-identical to today), in `tests/test_llm_provider.py` (contract T1)
- [x] T002-I Add `images: list[str] | None = None` to `Message` in `src/comfydv/_llm/provider.py` — makes T002-T pass

**Checkpoint**: carrier ready — user stories can begin.

---

## Phase 3: User Story 1 — Describe an image with a chat node (Priority: P1) 🎯 MVP

**Goal**: A workflow author wires a ComfyUI `IMAGE` into the existing `ChatCompletion` node and gets back a text description via an Ollama vision model; the text-only path is unchanged when no image is wired.

**Independent Test**: Wire an image → `ChatCompletion` → Ollama (vision model), confirm the response describes the image; un-wire the image and confirm behaviour/output identical to today.

- [x] T003-T [P] [US1] Write FAILING test: node-local `_encode_image_tensor()` converts a synthetic `[1,H,W,3]` float tensor (0..1) into a **decodable** base64 PNG, encodes a `B>1` batch to a list of that length, and returns `[]` for `None`/empty, in `tests/test_ollama.py` (contract T5; witnesses `features/us1_describe_image.feature` scenario "Describe a wired image")
- [x] T003-I [US1] Implement `_encode_image_tensor()` in `src/comfydv/ollama.py` — lazy `PIL`/`numpy` import so module import stays clean outside ComfyUI (Constitution IV); batch → one base64 string per frame — makes T003-T pass
- [x] T004-T [US1] Write FAILING test: `ChatCompletion.INPUT_TYPES` exposes an **optional** `image: ("IMAGE",)`; `RETURN_TYPES`/`RETURN_NAMES` positions are unchanged; an un-wired run builds the same text-only messages as today; a wired run attaches images to the **last user turn only** (history untouched), in `tests/test_ollama.py` (contract T6; witnesses both `features/us1_describe_image.feature` scenarios)
- [x] T004-I [US1] Add the optional `image` input (with a tooltip noting a vision-capable model is required; llama.cpp needs `--mmproj`) and attach encoded images to the appended user `Message` in `ChatCompletion.chat()` in `src/comfydv/ollama.py` — makes T004-T pass (depends on T003-I, T002-I)
- [x] T005-T [P] [US1] Write FAILING test: `OllamaProvider.chat()` forwards a message's images as a flat `images:[...]` array to `/api/chat`, and a text-only call's payload is **byte-identical to today** (regression), in `tests/test_ollama_provider.py` (contract T2; witnesses `features/us1_describe_image.feature` scenario "Describe a wired image")
- [x] T005-I [US1] Ensure `OllamaProvider.chat()` passes images through and omits the empty `images` key (e.g. `model_dump(exclude_none=True)`) in `src/comfydv/_llm/ollama_provider.py` — makes T005-T pass (depends on T002-I)

**Checkpoint**: describe-an-image works end-to-end on Ollama (MVP); every existing text-only test stays green.

---

## Phase 4: User Story 2 — Same image input on either backend (Priority: P1)

**Goal**: The same node and wiring drive image input on llama.cpp too, via its OpenAI-compatible content-parts shape — proving the generic-node promise (ADR-007/008) holds for the image path.

**Independent Test**: Run the US1 workflow unchanged against a llama.cpp server (launched with `--mmproj`); swap the Ollama client node for the llama.cpp one with no other change and confirm the image is still described.

- [x] T006-T [P] [US2] Write FAILING test: `LlamaCppProvider.chat()` maps a message's images into OpenAI `content` parts (`{"type":"text",...}` + `{"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}`) for `/v1/chat/completions`, and a text-only message keeps a **plain-string** `content` (regression), in `tests/test_llamacpp_provider.py` (contract T3; witnesses both `features/us2_both_backends.feature` scenarios)
- [x] T006-I [US2] Implement the images→content-parts mapping in `LlamaCppProvider.chat()` in `src/comfydv/_llm/llamacpp_provider.py`; leave text-only messages untouched — makes T006-T pass (depends on T002-I)

**Checkpoint**: parity proven — the identical node/wiring describes an image on both backends; swapping the client node is the only change.

---

## Phase 5: User Story 3 — Structured output about an image (Priority: P2)

**Goal**: Image input works with the node's existing structured-output mode, via the shared `chat_structured()` helper (pydantic-ai `BinaryContent`) — one implementation covering both backends through `OpenAIChatModel`.

**Independent Test**: Enable structured output with a schema, wire an image, run against a vision model, confirm each field is populated from the image with no required field blank; a first-invalid response retries then fails clearly.

- [x] T007-T [US3] Write FAILING test: `chat_structured()` attaches a message's images as `BinaryContent(data=b64decode(img), media_type="image/png")` onto the run's `user_prompt` (last turn) and onto history `UserPromptPart`s, a text-only structured call is unchanged, and the retry/validation contract is intact, in `tests/test_llm_chat_structured.py` (contract T4; witnesses both `features/us3_structured_image.feature` scenarios) — mock at the `Agent.run`/`_build_agent` seam per the established convention
- [x] T007-I [US3] Implement image→`BinaryContent` handling in `chat_structured()` and `_history_to_messages()` in `src/comfydv/_llm/chat.py` — makes T007-T pass (depends on T002-I)

**Checkpoint**: structured image output works on both backends via the one shared helper; all prior stories remain green.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T008 [P] Document image input on `ChatCompletion` in `README.md` and add a `CHANGELOG.md` Unreleased entry — note the vision-model / llama.cpp `--mmproj` prerequisite (quickstart.md)
- [x] T009 Run the full quality gate: `ruff check` ✓, `ruff format` ✓, `pytest` ✓ (289 passed, +21 new; all spec-009 code green), `beacon doctor --strict` ✓ for this spec (bullet + BDD + backlinks pass). _Pre-existing, out of scope: `ty check` has 36 diagnostics repo-wide (0 from spec-009 code — verified), one Docker packaging test (`test_dockerfile_uses_python_311_base`) fails at baseline, and `spec-task-alignment` flags 007's deferred tasks under --strict._
- [-] T010 End-to-end `quickstart.md` validation against a live vision backend (Ollama multimodal model and `llama-server --mmproj`) _Deferred — requires a live vision-capable backend not available in CI/this environment; validate manually before release._

---

## Dependencies & Execution Order

- **Setup (T001)** → no dependencies; start immediately.
- **Foundational (T002-T/I)** → depends on nothing; **blocks all user stories** (every path reads `Message.images`).
- **US1 (T003–T005)** → after T002-I. `T004-I` depends on `T003-I`; `T005-I` depends on `T002-I`. MVP.
- **US2 (T006)** → after T002-I. Independent of US1's files; independently testable.
- **US3 (T007)** → after T002-I. Independent of US1/US2's files; independently testable.
- **Polish (T008–T010)** → after the stories you intend to ship.

### Within each story

- The `-T` task is written and committed **failing** before its `-I` partner (`tdd-commit-discipline`).
- `-I` is never `[P]` with its own `-T`.

### Parallel opportunities

- US1: `T003-T` (`tests/test_ollama.py`) and `T005-T` (`tests/test_ollama_provider.py`) are different files → `[P]`.
- Across stories: US1, US2, US3 touch different provider/helper files and can proceed in parallel once T002-I lands.

---

## Parallel Example: User Story 1

```bash
# Different test files, no shared deps — write both failing tests together:
Task: "T003-T encode-helper test in tests/test_ollama.py"
Task: "T005-T Ollama image-passthrough test in tests/test_ollama_provider.py"
```

---

## Implementation Strategy

### MVP first (US1 only)

1. T001 Setup → T002 carrier → T003–T005 US1.
2. **STOP and VALIDATE**: an Ollama vision model describes a wired image; every text-only test stays green.
3. Demoable as-is.

### Incremental delivery

1. Foundation + US1 → describe-an-image on Ollama (MVP).
2. + US2 → same node works on llama.cpp (parity).
3. + US3 → structured output about an image (both backends).
4. Polish → docs, quality gate, manual live validation (T010).

---

## Notes

- `[-]` (T010) is a **known-deferred** follow-up — `beacon bullet finish` skips it rather than flipping to `[x]`; `beacon doctor` reports it as deferred, held under `--strict`.
- `beacon doctor` runs two gates against this discipline: `spec-bdd-coverage` (every acceptance scenario has a `.feature` witness — 6 scenarios across 3 features here) and `tdd-commit-discipline` (no test + implementation in the same commit). Both FAIL under `--strict`.
- Commit after each task or `-T`/`-I` pair; keep existing Ollama/llama.cpp/text tests green throughout (FR-003/SC-004 regression guard).
