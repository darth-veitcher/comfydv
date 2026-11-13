# LTX-2.3 I2V Multi-Agent Pipeline

`ltx-i2v-pipeline.json` wires the 6-agent prompt-compiler pipeline from
[`project-management/Work/planning/ltx.md`](../project-management/Work/planning/ltx.md)
onto comfydv's existing generic LLM nodes — `OllamaClient`, `ChatCompletion`
(structured output, image input) and `FormatString` (Jinja2 templating). No
new node code was needed; this is a wiring exercise, not a feature.

## Loading it

Two files, two purposes:

- **`ltx-i2v-pipeline-canvas.json`** — the canvas/UI format. Load this one
  via drag-and-drop or File > Open in ComfyUI. It's fully wired (20 nodes,
  52 links) and ready to run — no manual reconnecting required. It also
  includes two small conveniences not in the API-format file below: a
  shared **"Model Name"** `PrimitiveString` node feeding all 6
  `ChatCompletion` agents (edit the model in one place), and a **"User
  Intent"** `PrimitiveString` node holding the literal starting request
  text.
- **`ltx-i2v-pipeline.json`** — the ComfyUI **API-format** workflow
  (`{node_id: {class_type, inputs}}`). Use this to `POST` straight to
  `/prompt` for headless/scripted runs. **Do not drag-and-drop this one
  onto the canvas** — confirmed live: ComfyUI's generic API→graph importer
  doesn't trigger the dynamic-socket callbacks `ChatCompletion` (structured
  outputs) and `FormatString` (per-template-variable inputs) rely on, so
  nodes load with only their static fields and every dynamic link is
  silently dropped. `ltx-i2v-pipeline-canvas.json` was produced by loading
  this file, live-repairing exactly that gap against a real ComfyUI+Ollama
  instance (calling each node's own dynamic-socket routes directly, then
  replaying every link from this file by name), and saving the result —
  see "How this was verified" below.

## Prerequisites

- Ollama running locally with a model that has both `vision` and `tools`
  capability (check `ollama show <model>`'s `capabilities` list) — every
  agent in this pipeline uses `structured_output=True`, and some also need
  vision. Default baked into the workflow: `qwen3.5:9b`, used for every
  agent (text and vision alike) — edit the `model` field on each
  `ChatCompletion` node if you have something else installed.
  `lukey03/qwen3.5-9b-abliterated-vision` was tried and rejected: its
  chat template is degenerate enough that it returns valid-shaped but
  garbled content regardless of structured-output mechanism (see
  [ADR-009](../project-management/ADRs/ADR-009-native-structured-output-mode.md)).
- **Thinking is off by default.** Node `18` (`OllamaOptionDisableThinking`,
  `disable_thinking=True`) sits at the end of the options chain every
  `ChatCompletion` node reads from. Without it, a thinking-capable model
  routinely burns its whole `max_tokens` budget on chain-of-thought and
  never emits the closing JSON — `chat_structured` then fails validation
  against an empty string. Flip node `18`'s `disable_thinking` to `False`
  if you deliberately want a model to reason before answering; if you do,
  give it real headroom: nodes `16`/`17` set `max_tokens=8192`/`num_ctx=32768`
  for exactly that case, and Ollama's default context (4096, with
  `--context-shift` silently evicting old context rather than stopping)
  is nowhere near enough for these agents' long system prompts on top of
  reasoning tokens. Node `17`'s `num_ctx` reaches Ollama correctly because
  `OllamaProvider.chat_structured()` calls Ollama's *native* `/api/chat` +
  `"format"` directly (ADR-009) — an earlier version of this fix tried
  priming context via a separate call before the real request and that
  didn't work, because Ollama's OpenAI-compatible endpoint silently
  reloads the model at its default context on every call, undoing any
  priming; the native endpoint doesn't have that problem and applies
  `options` and structured output atomically in one request. Every
  `ChatCompletion` node's `timeout_secs=600` for the same headroom reason;
  lower it if your hardware is faster than the machine this was tuned
  against.
- To use `LlamaCppClient` instead of `OllamaClient`, swap node `1`'s
  `class_type` and `host` — every `ChatCompletion` node keeps working
  unchanged, since both emit the same `LLM_CLIENT` type (ADR-007). Note
  llama-server's context is fixed at process launch (`--ctx-size`), not
  a per-request setting — node `17`'s `num_ctx` only affects Ollama.
- Replace node `2`'s `image` filename with your actual starting frame.

## Status: confirmed working end-to-end against a live server

Ran to completion (`status: success`) against a real local Ollama server
(`qwen3.5:9b`), through the actual ComfyUI node graph, all 6 agents plus
the final-output node. Getting here took two real comfydv bugs, both fixed
and documented in [ADR-009](../project-management/ADRs/ADR-009-native-structured-output-mode.md):

1. Ollama's OpenAI-compatible endpoint silently reloads the model at its
   default (tiny) context size on every call, discarding any
   `options.num_ctx` — fixed by switching `OllamaProvider.chat_structured()`
   to Ollama's native `/api/chat` + `"format"`, which doesn't have that
   problem.
2. `_build_structured_model` (`src/comfydv/ollama.py`) typed non-required
   schema fields as bare `py_type` with a `None` default, which only
   covers a field being *omitted* — an explicit `null` in the model's JSON
   (which models routinely emit) failed pydantic validation. Fixed by
   typing those fields `py_type | None`.

**One remaining quirk, not a wiring bug:** `qwen3.5:9b` sometimes
under-attends to short/simple prompt content — in one full run it reported
Agent 1's `user_intent` as "no content provided" despite the field being
populated, which cascaded into an empty Director prompt, which the Judge
correctly caught (`decision: FAIL`) and the Refiner correctly attempted to
repair. That's the multi-agent design working as intended against a bad
upstream extraction — the fix for *that* is prompt/model tuning on Agent 1,
not a pipeline change. Re-run if you hit it; it isn't consistent.

```bash
# isolated single-agent test — much faster to debug than the full graph
python3 -c "
import json
d = json.load(open('ltx-i2v-pipeline.json'))
subset = {k: d[k] for k in ['1','2','16','17','3','4']}  # Agent 1 only
json.dump({'prompt': subset}, open('/tmp/agent1_only.json','w'))
"
curl -X POST http://localhost:8188/prompt -H "Content-Type: application/json" \
  --data @/tmp/agent1_only.json
```

## Pipeline shape

```
OllamaClient ─┬─────────────────────────────────────────────────────────┐
LoadImage ────┼──────────┬──────────┬──────────┬──────────┐             │
              │          │          │          │          │             │
FormatString→ChatCompletion (Agent 1: Intent Compiler)     [no image]   │
              │                                    │                     │
              FormatString→ChatCompletion (Agent 2: Scene Grounder) ←image
                                    │
              FormatString→ChatCompletion (Agent 3: Manifest Verifier) ←image
                                    │
       intent ─┴─ audited_manifest
              FormatString→ChatCompletion (Agent 4: Director) ←image
                                    │
       + intent + manifest ────────┴── candidate_prompt
              FormatString→ChatCompletion (Agent 5: Judge) ←image
                                    │
       + everything above ─────────┴── judge_report
              FormatString→ChatCompletion (Agent 6: Refiner)  [no image]
                                    │
              FormatString (Final Output — judge decision + both prompts)
```

## Deliberate adaptations from ltx.md

1. **Single round, no retry loop.** ltx.md's reference pseudocode runs
   `for iteration in range(2): judge → refine`, short-circuiting on PASS.
   ComfyUI graphs are DAGs with no native conditional/loop node in this repo
   (checked `circuit_breaker.py`, `random_choice.py` — neither fits), so a
   real retry loop can't be expressed as a static graph. This workflow always
   runs Judge once and Refiner once. The **Final Output** node (`15`) shows
   the Judge's `decision` next to *both* the Director's candidate prompt and
   the Refiner's patched prompt — read the decision and use the candidate
   prompt on PASS, the refined prompt on FAIL. Wire a second Judge/Refiner
   pair after node `14` yourself if you want the second round.

2. **Structured output carries whole objects, not just fields.**
   `ChatCompletion`'s `response` output is the full JSON object
   (`parsed.model_dump_json()`), and — since `structured_output=True` also
   adds one extra named output per top-level schema property — a specific
   nested object can be pulled out directly by name (e.g. Agent 3's
   `audited_manifest` output, used instead of its `response` wrapper, which
   also contains `verification`). Templates use `{{ x }}` directly rather
   than ltx.md's `{{ x | tojson(indent=2) }}`, since `x` arrives already
   JSON-encoded.

3. **List-valued template variables are JSON strings.** `FormatString`'s
   dynamic inputs are always `STRING`; there's no native list socket. Fields
   like `preservation_requirements` or `extraction_hints` are typed as JSON
   arrays (e.g. `["keep hairstyle"]`) and unpacked in-template with the
   `fromjson` filter your repo's `FormatString` already ships. Leave them as
   empty string `""` to omit the section entirely — falsy-string `{% if %}`
   checks guard every optional block, so `fromjson` is never called on an
   empty value.

4. **`output_schema` is intentionally shallow.** `ChatCompletion` only
   enforces *top-level* property types (see `_build_structured_model` in
   `src/comfydv/ollama.py`) — it doesn't validate nested structure. The
   detailed nested shape each agent must produce (e.g. every field inside
   `required_camera`) is still communicated to the model via the literal
   JSON example embedded in that agent's system prompt (verbatim from
   ltx.md), so nothing is lost — the `output_schema` JSON here just needs to
   get the top-level field list and types right, which is also all
   `ChatCompletion` uses it for.

5. **Required fields exclude anything legitimately blank.** A `required`
   *string* field is forced non-empty by `ChatCompletion`
   (`Field(..., min_length=1)`) to catch blank-output failures. Fields that
   are correctly empty on a non-nominal status — Director's `prompt` on
   `UNSATISFIABLE`, Judge's `refinement_instruction` on `PASS`, Refiner's
   `prompt`/`unresolvable_reason` — are deliberately left out of each
   schema's `required` list so a legitimate empty string doesn't trigger a
   retry loop against the model.

6. **Optional Agent 7 (Targeted Manifest Resolver) is not wired.** It only
   fires on a `MANIFEST_CHALLENGE`, which this static graph can't branch on.
   Add it manually if the Director or Judge start returning that status for
   your inputs.

## How this was verified

`ltx-i2v-pipeline-canvas.json` was produced against a live ComfyUI+Ollama
instance: loaded `ltx-i2v-pipeline.json` via the frontend's own
`app.loadApiJson`, then for every `ChatCompletion` node called its real
`/dv/ollama/update_structured_outputs` route (and for every `FormatString`
node its real `updateNodeConfig()`) with that node's own schema/template to
get its actual dynamic sockets, then replayed all 39 links from
`ltx-i2v-pipeline.json` by input name — zero errors — before saving. Every
expected connection was re-checked programmatically (not just visually)
against the saved file: 52 links total, and the only unconnected input
sockets are the intentionally-blank optional ones (`headers`, `history`,
the two non-vision agents' unused `image` input, and the Director's unset
shot-constraint overrides).

Everything in `ltx-i2v-pipeline.json` itself (the API-format source) was
separately checked against this repo's actual node code (not just read —
executed), with mocked `comfy`/`server`/`folder_paths` modules the way
`tests/conftest.py` does:

- Every `[node_id, index]` link target resolves to a real node.
- Every `FormatString` template's variables (via the same
  `jinja_env.parse` + `meta.find_undeclared_variables` AST extraction
  `_extract_keys` uses) exactly match the inputs supplied in the workflow.
- Every template renders through the real `FormatString.format_string()`
  with representative values, including the Director's `SHOT CONSTRAINTS`
  block, which was parsed back with `json.loads` to confirm it's valid JSON
  even when every optional field is left blank.
- Every `output_schema` parses through the real `_parse_output_schema`/
  `_build_structured_model`, and every link that targets a *named* structured
  output (e.g. `audited_manifest`, `prompt`, `decision`) was checked against
  the actual computed `(response, updated_history, model_name, *properties)`
  output order for that schema.
