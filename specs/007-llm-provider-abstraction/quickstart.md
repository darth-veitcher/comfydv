# Quickstart: LLM Provider Abstraction

A minimal ComfyUI workflow using the generic nodes this feature introduces.

## 1. Connect to a local server

Add an **Ollama Client** node. Set its host widget (default
`http://localhost:11434`). This is the only node that knows it's talking to
Ollama specifically — everything downstream just sees `LLM_CLIENT`.

## 2. Chat

Add a **Chat Completion** node. Wire the client node's `LLM_CLIENT` output
into it. Set a model name (or feed one from a model-selector node — see
below) and a prompt. Run the workflow: the node returns the model's text
response.

## 3. Get structured output instead of free text

On the same **Chat Completion** node, enable `structured_output` and supply
a JSON Schema (e.g. `{"type": "object", "properties": {"summary": {"type": "string"}, "score": {"type": "number"}}, "required": ["summary", "score"]}`).
Re-run: the node now exposes one typed output socket per schema property
(`summary`, `score`) instead of a single text blob, and guarantees neither
is blank.

## 4. Manage what's loaded in memory

Add an **LLM Model Selector** node wired to the same client, to see every
model the server knows about and its current status (`unloaded` /
`loading` / `loaded` / …). Add **LLM Load Model** / **LLM Unload Model**
nodes, wired to the same client, to explicitly control residency before a
chat node needs a model.

## 5. (Follow-on epic) Swap backends without touching downstream nodes

Once `llamacpp-integration` ships a **Llama.cpp Client** node, replacing the
**Ollama Client** node in step 1 with it — and nothing else — is the whole
migration: it emits the same `LLM_CLIENT` socket type, so every node from
steps 2–4 keeps working unmodified. That's the point of this feature.

## Migrating an existing pre-upgrade workflow

If you have a saved workflow using the old node names (`OllamaClient`,
`OllamaChatCompletion`, `OllamaModelSelector`, `OllamaLoadModel`,
`OllamaUnloadModel`), ComfyUI will report those node types as missing on
load. Replace each with its generic equivalent from the list above and
reconnect — behavior is unchanged, only the node names and the
`LLM_CLIENT` socket type (replacing `OLLAMA_CLIENT`) are different. See
`spec.md`'s User Story 4 and Edge Cases for the full detail.
