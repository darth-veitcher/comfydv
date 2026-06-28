# Epic: Ollama Model Integration

## Status
Planning  — started 2026-06-28

## Why now

`darth-veitcher/comfyui-ollama-model-manager` provides useful ComfyUI nodes for
driving local Ollama inference, but it's a separate repo with a critical open
bug (Issue #1 — model dropdown missing on two of the most-used nodes), its own
dependency on `loguru`/`rich` (conflicts ADR-001/002), and `httpx` (ADR-003 —
ComfyUI already ships `aiohttp`). Folding it into comfydv: consolidates the
offering under one maintained repo, fixes the bug during the migration, and
applies comfydv's established logging and dep policies. The old repo will be
archived after this epic ships.

## Dependencies

_None — no other epic must land first._

## Specs

_Filled by beacon specify --epic ollama-integration._

- specs/006-ollama-model-integration/
## ADRs

- project-management/ADRs/ADR-004-aiohttp-over-httpx-for-ollama.md — use aiohttp (already in ComfyUI's dep tree) instead of adding httpx; per ADR-003 policy
- project-management/ADRs/ADR-005-ollama-host-config-via-client-node.md — Ollama host URL is set once on an OllamaClient config node and threaded through via a custom `OLLAMA_CLIENT` socket type; nodes never hard-code localhost

## Success criteria

- All 14 Ollama nodes ported into `src/comfydv/` and registered in `NODE_CLASS_MAPPINGS`
- Issue #1 fixed: `OllamaLoadModel` and `OllamaChatCompletion` expose a live model dropdown populated from the Ollama `/api/tags` endpoint
- `loguru` and `rich` replaced by stdlib `logging`; `httpx` replaced by `aiohttp`
- `requirements.txt` updated (only new runtime deps not already in ComfyUI)
- All existing comfydv tests still pass; new nodes have test coverage
- CI smoke test passes
- `darth-veitcher/comfyui-ollama-model-manager` archived on GitHub; Issue #1 closed with pointer to comfydv

## Non-goals

- Serving Ollama remotely (only localhost/configurable host via client node — no auth, no TLS termination)
- Fine-tuning or model download management (pull, push) — just inference
- Adding Ollama nodes to the ComfyUI Manager registry in this epic (that's a separate PR to comfy-manager-entry.json, done post-ship)
- GPU inference optimisation — out of scope for a CPU-first dev harness

## Notes

**14 nodes to port** (from `comfyui-ollama-model-manager`):

| Node | Category |
|------|----------|
| `OllamaClient` | Config — holds host URL |
| `OllamaModelSelector` | Model management — dropdown, returns model name string |
| `OllamaLoadModel` | Model management — loads model into Ollama memory |
| `OllamaUnloadModel` | Model management — evicts model from Ollama memory |
| `OllamaChatCompletion` | Inference — single-turn or multi-turn with history |
| `OllamaDebugHistory` | Utilities — serialises a history list to string |
| `OllamaHistoryLength` | Utilities — returns len(history) |
| `OllamaOptionTemperature` | Composable options |
| `OllamaOptionSeed` | Composable options |
| `OllamaOptionMaxTokens` | Composable options |
| `OllamaOptionTopP` | Composable options |
| `OllamaOptionTopK` | Composable options |
| `OllamaOptionRepeatPenalty` | Composable options |
| `OllamaOptionExtraBody` | Composable options |

**Custom socket types:** `OLLAMA_CLIENT`, `OLLAMA_OPTIONS`, `OLLAMA_HISTORY`

**Issue #1 root cause:** Auto-fetch dropdown only wired on `OllamaModelSelector`;
`OllamaLoadModel` and `OllamaChatCompletion` use a plain string widget (no
`updateNodeConfig` call) — model must be typed manually. Fix: give all three
nodes the same dynamic dropdown backed by a `GET /api/tags` call.

**Web JS extension:** `web/ollama_widgets.js` (original) needs to be merged into
`src/js/` alongside the existing `dv_widgets.js`.

**Ollama available locally** (tested 2026-06-28):
- `http://localhost:11434` — Ollama v0.30.10
- Models: `lukey03/qwen3.5-9b-abliterated-vision:latest` (9.7B, vision)
- Models: `embeddinggemma:latest` (307M, embeddings)
