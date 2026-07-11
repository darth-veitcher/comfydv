# Quickstart: llama.cpp Model Integration

## Prerequisite

Launch `llama-server` in router mode:

```bash
llama-server --models-dir ./models -c 8192
```

## Minimal workflow

1. Add an **LlamaCpp Client** node. Set its host widget (default
   `http://localhost:8080`, llama-server's default port).
2. Wire it into a **Chat Completion** node — the exact same node used for
   Ollama. Set a model and prompt, run.
3. Structured output, model listing, and load/unload all work exactly as
   documented for Ollama in the main README/quickstart — swap the client
   node, nothing else changes.

## Swapping an existing Ollama workflow to llama.cpp

Replace the **Ollama Client** node with an **LlamaCpp Client** node, pointed
at your running `llama-server`. Every downstream node (Chat Completion, LLM
Model Selector, LLM Load Model, LLM Unload Model) keeps working unmodified —
this is the whole point of the provider abstraction (ADR-007).
