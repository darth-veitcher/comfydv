# Implementation Plan: Ollama Model Integration

**Branch**: `006-ollama-model-integration` | **Date**: 2026-06-28 | **Spec**: [spec.md](spec.md)

**Epic**: `project-management/Roadmap/epics/ollama-integration.md`

---

## Summary

Port 14 Ollama model management nodes from `darth-veitcher/comfyui-ollama-model-manager`
into `src/comfydv/`. Fix Issue #1 (Load Model and Chat Completion lack a model dropdown,
causing empty-model validation errors) by giving all three selection nodes the same JS-driven
dynamic model dropdown. Replace `loguru`/`rich` with stdlib `logging` (ADR-001/002) and
`httpx` with `aiohttp` (ADR-003/ADR-004). Ollama host is threaded through a typed
`OLLAMA_CLIENT` connection handle produced by an `OllamaClient` config node (ADR-005).
All nodes are tested with mocked HTTP calls; no live Ollama or ComfyUI instance is
required to run the test suite.

---

## Technical Context

**Language/Version**: Python 3.11 (per `docker/Dockerfile`)

**Primary Dependencies**:
- `aiohttp` (already in ComfyUI's dependency tree — used for all Ollama HTTP calls per ADR-004)
- `jinja2` (already a project runtime dep — not needed for Ollama nodes)
- ComfyUI node API (`INPUT_TYPES`, `RETURN_TYPES`, `RETURN_NAMES`, `FUNCTION`, `CATEGORY`)
- `PromptServer` from ComfyUI `server` module (runtime-guarded via `if "comfy" in sys.modules:`)
- JavaScript: ComfyUI extension API (`app.registerExtension`, `beforeRegisterNodeDef`)

**Storage**: N/A — no persistence beyond what Ollama manages server-side

**Testing**: `pytest` + `pytest-asyncio` (live Ollama at `http://localhost:11434`; no mocking
of HTTP calls — tests must exercise the real Ollama API). System-level tests use the
existing `docker-compose.dev.yml` harness via `just up-d`. See §Test Strategy below.

**Target Platform**: ComfyUI custom node; Python 3.11 process

**Performance Goals**: Model list refresh ≤ 2 s on localhost; inference latency dominated by
Ollama (not by these nodes); no added overhead beyond one HTTP round-trip per node execution

**Constraints**:
- No new HTTP dependency (ADR-004 — use `aiohttp`, already present)
- No new third-party logging library (ADR-001/002 — stdlib `logging` only)
- No new ComfyUI-provided packages in `requirements.txt` (ADR-003)
- Node FUNCTION methods are called synchronously by ComfyUI's executor; async Ollama calls
  are bridged with a `_run_async()` helper that creates a fresh event loop (avoids conflict
  with ComfyUI's running aiohttp loop)
- Integration tests require live Ollama at `http://localhost:11434` (always running locally;
  CI smoke test uses docker-compose and is explicitly permitted to skip Ollama-dependent
  tests if Ollama is unavailable in that environment)
- ComfyUI imports are runtime-guarded (`if "comfy" in sys.modules:`) so the module loads
  in test/CI environments without error

**Project Type**: ComfyUI custom node plugin (library)

---

## Constitution Check

*GATE: Must pass before implementation. Re-check before PR.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — ComfyUI Contract First | ✓ | All 14 nodes implement `INPUT_TYPES`, `RETURN_TYPES`, `RETURN_NAMES`, `FUNCTION`, `CATEGORY`; registered in `NODE_CLASS_MAPPINGS` |
| II — Sandbox All User-Supplied Code | N/A | Ollama nodes execute no user-supplied code; prompts are forwarded as strings |
| III — Test-First | ✓ (amended) | Tests are written before implementation. Ollama node tests use live Ollama at localhost:11434 — no HTTP mocking. Constitution amendment required: constitution §III says "pass without a live ComfyUI instance"; this is preserved (ComfyUI imports still guarded), but Ollama-dependent integration tests DO require a live Ollama. Tests are marked `@pytest.mark.integration` and `pytest.ini` gates confirm availability. See §Test Strategy. |
| IV — Graceful Degradation | ✓ | `if "comfy" in sys.modules:` guard on all ComfyUI imports; module loads cleanly in tests |
| V — Simplicity | ✓ | HTTP helpers (`_run_async`, `_fetch_models`, `_post_json`) are module-level functions; classes only for node registration pattern |
| VI — Fixed Output Positions | ✓ | `OllamaChatCompletion`: pos 0 = `response` (STRING), pos 1 = `updated_history` (OLLAMA_HISTORY) |

No constitution violations. No Complexity Tracking entry required.

---

## Phase 0: Research

### Research Summary

All unknowns were resolved from codebase inspection and Ollama API documentation
(tested against live localhost instance at `http://localhost:11434`, Ollama v0.30.10).

#### R-01: Async bridging (sync node execution ↔ async aiohttp)

**Decision**: `asyncio.new_event_loop()` helper function.

```python
def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```

**Rationale**: ComfyUI's node executor calls `FUNCTION` methods synchronously. ComfyUI's
web server runs an aiohttp event loop on the main thread. Creating a *new* event loop
in the executor's thread is safe — it does not interact with the main loop. `asyncio.run()`
was considered but rejected because it calls `loop.close()` after creation, which can
interfere with thread-local state in CPython 3.11.

**Alternatives rejected**: `asyncio.run()` (event loop conflict risk), `ThreadPoolExecutor`
wrapping `asyncio.run()` (over-engineering for simple REST calls).

#### R-02: Model dropdown strategy (Issue #1 fix)

**Decision**: Two-layer approach matching the existing `format_string.js` pattern:

1. **Python** (`INPUT_TYPES`): Model inputs on `OllamaModelSelector`, `OllamaLoadModel`,
   `OllamaChatCompletion` use a static `COMBO` with a list populated at module load from
   `http://localhost:11434/api/tags` (graceful fallback to `["(start Ollama to see models)"]`
   if unreachable).
2. **Python** (PromptServer route): `GET /dv/ollama/models?host=<url>` returns current
   model list from any host, for JS runtime refresh.
3. **JavaScript** (`ollama.js`): Registers an extension that hooks `beforeRegisterNodeDef`
   for `OllamaModelSelector`, `OllamaLoadModel`, `OllamaChatCompletion`. On node creation,
   calls `/dv/ollama/models?host=...` (reading host from the connected `OllamaClient` widget)
   and populates the dropdown. Adds a "⟳" refresh button.

**Why this fixes Issue #1**: The original `OllamaLoadModel` and `OllamaChatCompletion` had
`"model": ("STRING", {})` — plain text boxes with no dropdown wiring. The fix is:
(a) change them to `COMBO` in Python so they render as dropdowns even at startup, and
(b) wire the same JS hook that `OllamaModelSelector` uses so they refresh dynamically.

#### R-03: OLLAMA_CLIENT typed socket

**Decision**: A thin `str` subclass (same pattern as `AnyType` in `utils.py`), registered
as a ComfyUI custom type. At runtime the value is the host URL string.

```python
class OllamaClientType(str):
    """Typed host URL for Ollama connection — prevents accidental wiring to string sockets."""
```

All nodes that accept `OLLAMA_CLIENT` pull the host URL from this value directly.

#### R-04: Ollama API endpoints used

| Endpoint | Method | Nodes |
|----------|--------|-------|
| `/api/tags` | GET | Model list fetch (selector, load model, chat completion dropdowns) |
| `/api/generate` | POST | `OllamaChatCompletion` (non-chat models) |
| `/api/chat` | POST | `OllamaChatCompletion` (chat models, history support) |
| `/api/show` | POST | `OllamaLoadModel` (load / keep-alive) |
| `/api/show` | POST (keep_alive=0) | `OllamaUnloadModel` |

**Rationale**: Ollama v0.30+ uses `/api/show` with `keep_alive` to control model
residency. `/api/load` does not exist in the REST API; the original repo used it
incorrectly. Correct approach: `POST /api/show {"model": "...", "keep_alive": "5m"}` to load,
`POST /api/show {"model": "...", "keep_alive": 0}` to unload.

---

## Phase 1: Design

### Source code structure

```text
src/comfydv/
├── __init__.py          ← updated: import ollama module; 14 new entries in NODE_CLASS_MAPPINGS
├── ollama.py            ← NEW: all 14 node classes + PromptServer routes
├── circuit_breaker.py   ← unchanged
├── format_string.py     ← unchanged
├── random_choice.py     ← unchanged
└── utils.py             ← unchanged (AnyType lives here; OllamaClientType goes in ollama.py)

src/js/
├── format_string.js     ← unchanged
├── dynamic.js           ← unchanged
└── ollama.js            ← NEW: dynamic model dropdown widget + refresh button

tests/
├── test_ollama.py       ← NEW: unit tests for all 14 nodes (mocked aiohttp)
├── conftest.py          ← may need minor additions (async fixtures)
├── test_format_string.py ← unchanged
├── test_logging.py      ← unchanged
└── test_packaging.py    ← updated: add new nodes to packaging assertions
```

**Structure decision**: Single `ollama.py` file (Constitution V — Simplicity). The 14 nodes
divide naturally into 5 groups (client, model management, inference, utilities, options)
and fit in one module with section comments. If the file exceeds ~600 lines, split into
`ollama/` subpackage — but don't pre-optimise.

### Data model

**`OLLAMA_CLIENT`** (`OllamaClientType` — str subclass):
- Value: host URL string, e.g. `"http://localhost:11434"`
- Produced by: `OllamaClient.create_client()`
- Consumed by: All 4 primary nodes (selector, load, unload, chat completion)

**`OLLAMA_OPTIONS`** (Python `dict`):
- Keys: subset of `{"temperature", "seed", "num_predict", "top_p", "top_k", "repeat_penalty"}` plus `"extra_body"` (arbitrary JSON dict)
- Produced by: Each option node merges its key into the upstream options dict and outputs the result
- Consumed by: `OllamaChatCompletion` forwards the dict as the `options` field in the Ollama API payload

**`OLLAMA_HISTORY`** (Python `list[dict]`):
- Each element: `{"role": "user"|"assistant", "content": str}`
- Produced by: `OllamaChatCompletion` appends the new turn to the incoming history and outputs the extended list
- Consumed by: `OllamaChatCompletion` (prior turns), `OllamaDebugHistory`, `OllamaHistoryLength`

### Interface contracts

#### `/dv/ollama/models` (GET) — PromptServer route

```
GET /dv/ollama/models?host=http%3A%2F%2Flocalhost%3A11434

200 OK
Content-Type: application/json
{
  "models": ["llama3.2:latest", "embeddinggemma:latest"]
}

503 Service Unavailable
{
  "error": "Cannot reach Ollama at http://localhost:11434: <reason>"
}
```

Called by `ollama.js` when refreshing dropdowns. Never called during node execution.

#### ComfyUI node contracts (14 nodes)

| Node | RETURN_TYPES | RETURN_NAMES | Key inputs |
|------|-------------|--------------|-----------|
| `OllamaClient` | `("OLLAMA_CLIENT",)` | `("client",)` | `host: STRING` (default `http://localhost:11434`) |
| `OllamaModelSelector` | `("STRING",)` | `("model",)` | `client: OLLAMA_CLIENT`, `model: COMBO` |
| `OllamaLoadModel` | `("STRING",)` | `("model",)` | `client: OLLAMA_CLIENT`, `model: COMBO` |
| `OllamaUnloadModel` | `("STRING",)` | `("model",)` | `client: OLLAMA_CLIENT`, `model: STRING` |
| `OllamaChatCompletion` | `("STRING", "OLLAMA_HISTORY")` | `("response", "updated_history")` | `client`, `model: COMBO`, `prompt: STRING`, `system?: STRING`, `history?: OLLAMA_HISTORY`, `options?: OLLAMA_OPTIONS` |
| `OllamaDebugHistory` | `("STRING",)` | `("debug",)` | `history: OLLAMA_HISTORY` |
| `OllamaHistoryLength` | `("INT",)` | `("length",)` | `history: OLLAMA_HISTORY` |
| `OllamaOptionTemperature` | `("OLLAMA_OPTIONS",)` | `("options",)` | `options?: OLLAMA_OPTIONS`, `temperature: FLOAT` |
| `OllamaOptionSeed` | `("OLLAMA_OPTIONS",)` | `("options",)` | `options?: OLLAMA_OPTIONS`, `seed: INT` |
| `OllamaOptionMaxTokens` | `("OLLAMA_OPTIONS",)` | `("options",)` | `options?: OLLAMA_OPTIONS`, `max_tokens: INT` |
| `OllamaOptionTopP` | `("OLLAMA_OPTIONS",)` | `("options",)` | `options?: OLLAMA_OPTIONS`, `top_p: FLOAT` |
| `OllamaOptionTopK` | `("OLLAMA_OPTIONS",)` | `("options",)` | `options?: OLLAMA_OPTIONS`, `top_k: INT` |
| `OllamaOptionRepeatPenalty` | `("OLLAMA_OPTIONS",)` | `("options",)` | `options?: OLLAMA_OPTIONS`, `repeat_penalty: FLOAT` |
| `OllamaOptionExtraBody` | `("OLLAMA_OPTIONS",)` | `("options",)` | `options?: OLLAMA_OPTIONS`, `extra_body: STRING` (JSON) |

**Category** for all 14 nodes: `"dv/ollama"`

**Output position contract** (Constitution VI):
- `OllamaChatCompletion`: position 0 = `response` (STRING), position 1 = `updated_history` (OLLAMA_HISTORY). Fixed; cannot change after first release.
- All other nodes: single primary output at position 0.

### `__init__.py` additions

```python
from .ollama import (
    OllamaClient, OllamaModelSelector, OllamaLoadModel, OllamaUnloadModel,
    OllamaChatCompletion, OllamaDebugHistory, OllamaHistoryLength,
    OllamaOptionTemperature, OllamaOptionSeed, OllamaOptionMaxTokens,
    OllamaOptionTopP, OllamaOptionTopK, OllamaOptionRepeatPenalty,
    OllamaOptionExtraBody,
)

NODE_CLASS_MAPPINGS.update({
    "OllamaClient": OllamaClient,
    "OllamaModelSelector": OllamaModelSelector,
    # ... all 14
})

NODE_DISPLAY_NAME_MAPPINGS.update({
    "OllamaClient": "Ollama Client",
    "OllamaModelSelector": "Ollama Model Selector",
    # ... all 14 with human-readable names
})
```

### `ollama.py` internal structure

```
# 1. stdlib imports
# 2. ComfyUI runtime guard (if "comfy" in sys.modules)
# 3. logger = logging.getLogger(__name__)
# 4. OllamaClientType (str subclass)
# 5. _run_async() helper
# 6. _fetch_models(host) → list[str]     (async, returns graceful fallback on error)
# 7. _post_json(url, payload) → dict     (async, raises on HTTP error)
#
# --- Node classes (grouped with section comments) ---
# 8.  OllamaClient
# 9.  OllamaModelSelector
# 10. OllamaLoadModel
# 11. OllamaUnloadModel
# 12. OllamaChatCompletion
# 13. OllamaDebugHistory
# 14. OllamaHistoryLength
# 15. OllamaOption* × 7
#
# --- PromptServer routes (ComfyUI runtime only) ---
# 16. GET /dv/ollama/models
#
# --- Node mappings (module-level, for __init__.py) ---
# 17. NODE_CLASS_MAPPINGS (partial — merged into package __init__)
```

### Test strategy

**Principle**: Ollama integration tests exercise the real REST API — no mocking. The
integration behaviour we need to verify (correct endpoint, correct JSON shape, correct
error handling) cannot be meaningfully tested by asserting that `aiohttp.post` was called
with particular arguments. Only a live round-trip proves the integration works.

#### Three test layers

| Layer | Marker | Requires | Runner |
|-------|--------|----------|--------|
| Unit | *(none)* | Nothing — tests pure Python logic (option-dict merging, history append, JSON parse, type guards) | `uv run pytest -m "not integration and not system"` |
| Integration | `@pytest.mark.integration` | Live Ollama at `http://localhost:11434` | `uv run pytest -m integration` |
| System | `@pytest.mark.system` | Live Ollama + ComfyUI docker-compose harness (`just up-d`) | `just test-system` |

**Default `uv run pytest` runs ALL marks** (unit + integration). Ollama is always
running locally, so the full suite runs without flags during development.

CI smoke (`just ci-smoke`) only asserts that ComfyUI starts and all 14 nodes register
without errors — it does not exercise inference. Integration/system tests are run
separately by the developer before opening a PR.

#### `conftest.py` additions

```python
import pytest
import aiohttp
import asyncio

def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires live Ollama at localhost:11434")
    config.addinivalue_line("markers", "system: requires docker-compose harness")

@pytest.fixture(scope="session")
def ollama_host():
    return "http://localhost:11434"

@pytest.fixture(scope="session")
def ollama_available(ollama_host):
    async def check():
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{ollama_host}/api/tags", timeout=aiohttp.ClientTimeout(total=3)) as r:
                    return r.status == 200
        except Exception:
            return False
    return asyncio.get_event_loop().run_until_complete(check())

@pytest.fixture(autouse=True)
def skip_if_no_ollama(request, ollama_available):
    if request.node.get_closest_marker("integration") and not ollama_available:
        pytest.skip("Ollama not reachable at localhost:11434")
```

#### `test_ollama.py` structure

```python
# Unit tests (no marker) — pure logic, no I/O
def test_option_merge_temperature():  ...
def test_option_merge_seed_extends_existing_options():  ...
def test_history_length_empty():  ...
def test_debug_history_formats_turns():  ...
def test_extra_body_invalid_json_raises():  ...

# Integration tests — live Ollama required
@pytest.mark.integration
async def test_fetch_models_returns_list(ollama_host):
    models = await _fetch_models(ollama_host)
    assert isinstance(models, list)
    assert len(models) > 0

@pytest.mark.integration
async def test_client_node_outputs_host(ollama_host):
    node = OllamaClient()
    (client,) = node.create_client(host=ollama_host)
    assert client == ollama_host

@pytest.mark.integration
async def test_model_selector_lists_models(ollama_host):
    node = OllamaModelSelector()
    # selector's function calls /api/tags and returns first model name
    (model,) = node.select_model(client=ollama_host, model="embeddinggemma:latest")
    assert model == "embeddinggemma:latest"

@pytest.mark.integration
async def test_load_model(ollama_host):
    node = OllamaLoadModel()
    (model,) = node.load_model(client=ollama_host, model="embeddinggemma:latest")
    assert model == "embeddinggemma:latest"

@pytest.mark.integration
async def test_chat_completion_returns_response(ollama_host):
    node = OllamaChatCompletion()
    response, history = node.chat(
        client=ollama_host,
        model="lukey03/qwen3.5-9b-abliterated-vision:latest",
        prompt="Say exactly: pong",
        system="",
        history=[],
        options={},
    )
    assert isinstance(response, str) and len(response) > 0
    assert len(history) == 2  # user turn + assistant turn

@pytest.mark.integration
async def test_chat_completion_multi_turn(ollama_host):
    node = OllamaChatCompletion()
    _, h1 = node.chat(client=ollama_host, model="lukey03/qwen3.5-9b-abliterated-vision:latest",
                      prompt="My name is Alice.", system="", history=[], options={})
    response, h2 = node.chat(client=ollama_host, model="lukey03/qwen3.5-9b-abliterated-vision:latest",
                      prompt="What is my name?", system="", history=h1, options={})
    assert "Alice" in response
    assert len(h2) == 4  # 2 turns × (user + assistant)

@pytest.mark.integration
async def test_unload_model(ollama_host):
    node = OllamaUnloadModel()
    (model,) = node.unload_model(client=ollama_host, model="embeddinggemma:latest")
    assert model == "embeddinggemma:latest"

@pytest.mark.integration
async def test_unreachable_host_raises():
    node = OllamaChatCompletion()
    with pytest.raises(Exception, match="Cannot reach Ollama"):
        node.chat(client="http://localhost:19999", model="any", prompt="hi",
                  system="", history=[], options={})
```

#### Justfile additions

```just
# Run all tests (unit + integration; requires live Ollama)
test:
    uv run pytest -v

# Run only unit tests (no live services required)
test-unit:
    uv run pytest -v -m "not integration and not system"

# Run integration tests against live Ollama
test-integration:
    uv run pytest -v -m integration

# Run system tests against docker-compose harness (starts harness if not running)
test-system:
    {{dev}} up -d
    @until docker compose -f docker-compose.yml -f docker-compose.dev.yml ps --format json | python3 -c "import sys,json; s=[c for c in json.load(sys.stdin) if c.get('Name','').endswith('comfyui')]; exit(0 if s and s[0].get('Health')=='healthy' else 1)" 2>/dev/null; do sleep 3; done
    uv run pytest -v -m system
```

#### Constitution amendment

The constitution §III says "Tests must pass without a live ComfyUI instance." This remains
true — all ComfyUI imports are runtime-guarded and the unit test layer passes with no
live services. However, the integration test layer explicitly requires live Ollama. This
is a deliberate, scoped amendment: Ollama integration is meaningless to test without Ollama.
An ADR is **not** required for this (it is within the spirit of §III — ComfyUI-independence
is preserved); it is noted here for transparency.

---

### Key implementation notes

**`OllamaOptionExtraBody`**: Accepts a JSON string widget. Parses with `json.loads()`
and merges into the options dict. If invalid JSON, raises a descriptive `ValueError` (not a crash).

**`OllamaUnloadModel`**: Sends `POST /api/show {"model": "...", "keep_alive": 0}`.
Outputs the model name string (for chaining). If Ollama responds with 404 (model not
found), surfaces a clear error.

**`OllamaChatCompletion`**: Uses `/api/chat` (supports multi-turn history). System
prompt is an optional STRING input. If history is `None` (not connected), the upstream
history defaults to `[]`. The returned `updated_history` always has the new turn
appended — even if the model returned an empty string.

**Model dropdown initial population**: At `ollama.py` import time, `_run_async(_fetch_models("http://localhost:11434"))` populates a module-level `_DEFAULT_MODELS` list. Node `INPUT_TYPES()` uses `_DEFAULT_MODELS` as the static COMBO list. This is graceful: if Ollama isn't running, `_DEFAULT_MODELS = ["(start Ollama to see models)"]`. The JS widget overrides this with the live list at runtime.

---

## Project Structure Summary

```text
specs/006-ollama-model-integration/
├── plan.md              ← this file
├── research.md          ← embedded above (Phase 0 findings)
├── data-model.md        ← embedded above (Phase 1 design)
├── contracts/           ← documented inline above
└── tasks.md             ← Phase 2 output (run /beacon.tasks)
```

Source tree impact: 2 new Python files, 1 new JS file, 3 modified files (`__init__.py`,
`tests/test_packaging.py`, possibly `conftest.py`).
