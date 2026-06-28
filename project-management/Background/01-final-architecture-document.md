# Architecture Document

<!--
BEACON DESIGN phase deliverable. Update when a new ADR affects the architecture.
Always link to the relevant ADR rather than duplicating rationale here.
Use /design:diagram <component> to generate or regenerate any diagram below.
-->

## Overview

`comfydv` is a ComfyUI custom-node package. It is loaded by ComfyUI at startup from the `custom_nodes/` directory. The package exposes three nodes via `NODE_CLASS_MAPPINGS` and a JavaScript web directory via `WEB_DIRECTORY`. All node logic is pure Python; the JS layer handles dynamic UI updates (adding/removing input sockets when a template changes).

---

## C4 Context: System in its Environment

```mermaid
C4Context
    title System Context — comfydv
    Person(user, "Workflow Creator", "ComfyUI power user building parameterised pipelines")
    System(comfydv, "comfydv", "Custom node pack: FormatString, RandomChoice, CircuitBreaker")
    System_Ext(comfyui, "ComfyUI", "Host application — loads custom nodes, executes workflows")
    System_Ext(jinja2, "Jinja2 (SandboxedEnvironment)", "Template rendering engine")

    Rel(user, comfyui, "Designs and runs workflows", "Browser UI")
    Rel(comfyui, comfydv, "Loads nodes at startup; executes node functions during queue runs")
    Rel(comfydv, jinja2, "Renders sandboxed templates")
```

---

## C4 Container: Deployable Units

```mermaid
C4Container
    title Container Diagram — comfydv
    Person(user, "Workflow Creator", "")

    System_Boundary(comfyui, "ComfyUI Host") {
        Container(server, "ComfyUI Server", "Python / aiohttp", "Hosts the workflow engine and web API")
        Container(comfydv, "comfydv package", "Python 3.10+", "FormatString, RandomChoice, CircuitBreaker nodes + JS UI layer")
    }

    Rel(user, server, "Uses", "Browser / HTTP")
    Rel(server, comfydv, "Imports at startup; calls node FUNCTION during queue execution")
    Rel(comfydv, server, "Registers aiohttp routes: /update_format_string_node, /load_format_string_node, /get_format_string_node_config/{id}")
```

---

## System Components (logical view)

```mermaid
graph TB
    subgraph "comfydv"
        FS[FormatString]
        RC[RandomChoice]
        CB[CircuitBreaker]
        FS --> JE[(Jinja2 SandboxedEnv)]
    end
    subgraph "ComfyUI"
        Server[PromptServer / aiohttp]
        NodeReg[NODE_CLASS_MAPPINGS]
    end
    FS -->|registers routes on| Server
    NodeReg -->|maps| FS
    NodeReg -->|maps| RC
    NodeReg -->|maps| CB
    subgraph "src/js"
        JS[format_string.js / dynamic.js]
    end
    Server -->|serves| JS
    JS -->|POST /update_format_string_node| Server
```

---

## Technology Stack

| Layer | Technology | Rationale | ADR |
|-------|-----------|-----------|-----|
| Language | Python 3.10+ | ComfyUI minimum | — |
| Package manager | uv | Speed, lockfiles | — |
| Linter/formatter | Ruff | Single tool, replaces flake8+black+isort | — |
| Type checking | ty | Astral native, replaces mypy | — |
| Template engine | Jinja2 (SandboxedEnvironment) | Sandboxed evaluation of user templates | — |
| Web framework | aiohttp (via ComfyUI's PromptServer) | ComfyUI's built-in; no additional server needed | — |
| Testing | pytest + pytest-cov | Standard Python; mocks out ComfyUI imports | — |
| Docs | mkdocs-material + mkdocstrings | Generates API docs from docstrings | — |

---

## Data Flow: FormatString (primary path)

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant BrowserJS as Browser JS
    participant AiohttpRoute as /update_format_string_node
    participant FormatString
    participant Jinja2

    User->>BrowserJS: Edits template widget
    BrowserJS->>AiohttpRoute: POST {nodeId, template_type, template}
    AiohttpRoute->>FormatString: update_widget(node_id, template_type, template)
    FormatString-->>AiohttpRoute: updated config (inputs, outputs)
    AiohttpRoute-->>BrowserJS: JSON config
    BrowserJS-->>User: Sockets updated on node

    User->>FormatString: Queue prompt (ComfyUI executes format_string())
    FormatString->>Jinja2: render(template, context) [Jinja2 mode]
    Jinja2-->>FormatString: rendered string
    FormatString-->>User: (formatted_string, saved_file_path, var1, var2, ...)
```

---

## Output Order Contract (immutable)

FormatString outputs **must** be returned in this order — changing it breaks existing workflow connections silently:

| Index | Name | Type | Notes |
|-------|------|------|-------|
| 0 | `formatted_string` | STRING | Primary output |
| 1 | `saved_file_path` | STRING | Empty string if `save_path` not set |
| 2+ | `<variable_name>` | STRING | One per detected template variable, in order of first appearance |

---

## Non-Functional Requirements

- **Performance:** Template rendering is synchronous and CPU-bound; typical templates render in <1 ms. No caching layer needed at this scale.
- **Security:** Jinja2 `SandboxedEnvironment` prevents filesystem/subprocess access from user templates. `additional_context` is the only way to expose utilities.
- **Testability:** All node core logic (`_extract_keys`, `format_string`, `update_widget`) must be callable from pytest without a ComfyUI process. ComfyUI-specific imports are guarded by `if "comfy" in sys.modules`.
- **Observability:** `logging.getLogger(__name__)` at DEBUG level inside nodes; `rich.print` for user-visible output in the ComfyUI console.

---

## Tracer Bullet Decomposition

| Phase | Bullets | Outcome |
|-------|---------|---------|
| Bootstrap | 1 | BEACON artefacts populated; quality gates clean |
| Test hardening | 2 | Full unit coverage for all three nodes |
| Documentation | 3 | mkdocs site reflects current API |
| Distribution | 4+ | ComfyUI Manager listing; PyPI release |

---

_Created:_ 2026-06-28  
_Last updated:_ 2026-06-28 — initial DESIGN artefact  
_Status:_ Living document — update when ADRs change the architecture
