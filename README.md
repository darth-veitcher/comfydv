# comfydv

A collection of workflow efficiency and quality-of-life nodes built out of necessity for personal ComfyUI use.

## What is this?

`comfydv` fills gaps in ComfyUI's built-in node library: dynamic string formatting, seed-controlled random selection, graceful workflow interruption, and local LLM integration (Ollama and llama.cpp). Install it once and connect the nodes like any other — no Python knowledge required.

| Node | What it does |
|------|-------------|
| **Format String** | Formats a string from a Python f-string or Jinja2 template. Detects variables in the template and automatically adds/removes input sockets. |
| **Random Choice** | Accepts any number of typed inputs and outputs one at random, with a configurable seed for reproducibility. |
| **Circuit Breaker** | Halts the current ComfyUI queue run gracefully without crashing the server. Wire the `status` toggle to a boolean condition to skip the rest of the queue when a condition isn't met. |
| **Ollama Client** | Configures a connection to an Ollama server (default: `http://localhost:11434`). Threads the connection through the graph as an `LLM_CLIENT` socket — a generic connection type any backend's client node emits. |
| **LlamaCpp Client** | Configures a connection to a `llama-server` instance running in router mode (default: `http://localhost:8080`). Emits the same `LLM_CLIENT` socket as Ollama Client — every node below works with either. |
| **LLM Model Selector** | Fetches the live model list from the connected server and presents it as a dropdown. Outputs the selected model name. |
| **LLM Load Model** | Loads a model into memory on the connected server. |
| **LLM Unload Model** | Evicts a model from memory on the connected server. |
| **Chat Completion** | Sends a prompt (and optional conversation history) to the connected server. Response and history are shown inline in the node body and available as output sockets. |
| **Ollama Option — \*** | Seven composable option nodes (Temperature, Seed, Max Tokens, Top P, Top K, Repeat Penalty, Extra Body) that merge into an `OLLAMA_OPTIONS` dict wired into Chat Completion. |
| **Ollama Debug History** | Serialises an `OLLAMA_HISTORY` list to a pretty-printed JSON string for inspection. |
| **Ollama History Length** | Returns the number of messages in an `OLLAMA_HISTORY` list as an integer. |

## Install

**Via ComfyUI Manager** (recommended): search for `comfydv` and click Install.

**Manual:**

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/darth-veitcher/comfydv.git
```

Restart ComfyUI. The nodes appear under the **dv/**, **dv/ollama**, and **dv/llamacpp** categories in the node menu. Runtime dependencies (`jinja2`, `aiohttp`, `pydantic-ai`) are installed automatically via `requirements.txt`.

For local LLM nodes, pick one backend (or both):

- **Ollama**: [install Ollama](https://ollama.com/download) and pull at least one model (`ollama pull qwen2.5:latest`).
- **llama.cpp**: [build/install `llama-server`](https://github.com/ggml-org/llama.cpp) and launch it in router mode (`llama-server --models-dir ./models`) — see the [llama.cpp section](#llamacpp) below.

## Quickstart

1. Install via ComfyUI Manager (search `comfydv`) or clone manually into `custom_nodes/`.
2. Right-click the canvas → Add Node → **dv/** to find Format String, Random Choice, and Circuit Breaker.
3. For local LLM nodes: start Ollama (`ollama serve`) or `llama-server` (router mode), then add nodes from **dv/ollama/** or **dv/llamacpp/** — the chat/model-management nodes are shared between both backends.

## Documentation

Full documentation: [darth-veitcher.github.io/comfydv](https://darth-veitcher.github.io/comfydv/stable/)

---

## Format String

Formats text from a Python f-string or Jinja2 template. As you type the template, input sockets appear and disappear automatically — one per variable detected.

### Python f-strings

Type `{variable_name}` and a socket appears. Wire it to any string output in your workflow.

![Format String — f-string mode](docs/assets/fstring.png)

Outputs are always in a stable order:

| Output | Content |
|--------|---------|
| `formatted_string` | The rendered result |
| `saved_file_path` | Path written to disk (if `save_path` is set) |
| `<var>` … | Pass-through of each input value, for easy chaining |

### Jinja2 templates

Switch `template_type` to **Jinja2** to unlock filters (`| upper`, `| int`, …), conditionals (`{% if %}…{% endif %}`), and loops.

![Format String — Jinja2 mode](docs/assets/jinja2.png)

Variables detected in `{{ }}` expressions become input sockets exactly as in Simple mode. See the [Jinja2 documentation](https://jinja.palletsprojects.com/en/latest/) for the full filter/test reference.

---

## Random Choice

Connect any number of inputs of the same type. Each run picks one at random. Set `seed` for reproducibility.

![Random Choice](docs/assets/random.png)

- Accepts any ComfyUI type (STRING, IMAGE, CONDITIONING, …)
- Add as many inputs as you like; unused slots are removed automatically when disconnected
- `seed = 0` randomises on every run; any other value locks the selection

---

## Circuit Breaker

Stops the queue gracefully when a condition isn't met — no crash, no error, just a clean halt.

![Circuit Breaker](docs/assets/circuit_breaker.png)

Wire an image (or any trigger) into `trigger` and a boolean into `status`. When `status` is **false** the node raises `InterruptProcessingException`, which tells ComfyUI to stop the current run cleanly. When `status` is **true** the image passes through unchanged.

Typical use: skip an expensive upscale step when a quality-check node says the draft is already good enough.

---

## Ollama

Nodes for integrating a local Ollama LLM into your ComfyUI workflow. The host is configured once in **Ollama Client** and threaded through the graph as an `LLM_CLIENT` socket — a generic connection type any future backend's client node can also emit, so the chat/model-management nodes below aren't Ollama-specific.

### Ollama Client node

Configure the server address once; all downstream nodes inherit it automatically.

![Ollama Client](docs/assets/ollama_client.png)

### Model lifecycle (load and unload)

On memory-constrained machines and single-GPU setups, explicitly loading and unloading the model before and after inference is critical. **LLM Load Model** pins the model into VRAM (`keep_alive=-1`); **LLM Unload Model** evicts it immediately (`keep_alive=0`), freeing memory for image generation or other models.

![Ollama Load / Unload](docs/assets/ollama_lifecycle.png)

The correct chain is **Load → Chat → Unload**, enforced through data dependencies:

1. Wire `LLMLoadModel.model_name` → `ChatCompletion.model`. This creates the data dependency that guarantees Load runs before Chat and passes the model name into the Chat node's plain-string `model` input.
2. Wire `ChatCompletion.model_name` → `LLMUnloadModel.model`. This guarantees Unload runs after Chat completes.
3. Optionally wire `ChatCompletion.response` → `LLMUnloadModel.passthrough` — Unload returns the response unchanged so the rest of your workflow can still consume it.

### Minimal chat workflow

1. **Ollama Client** → set host (default `http://localhost:11434`)
2. **LLM Model Selector** → pick a model from the live dropdown (or type/wire a model name directly into Chat Completion's `model` input)
3. **Chat Completion** → wire client + model + prompt; the response appears inline in the node body and is also available as an output socket

![Chat Completion](docs/assets/ollama_chat.png)

Wire multiple nodes together for a complete end-to-end workflow:

![Ollama Full Workflow](docs/assets/ollama_workflow.png)

### Option nodes

Chain any combination of **Ollama Option —** nodes before Chat Completion to override inference parameters:

| Option node | Ollama param |
|-------------|-------------|
| Temperature | `temperature` |
| Seed | `seed` |
| Max Tokens | `num_predict` |
| Top P | `top_p` |
| Top K | `top_k` |
| Repeat Penalty | `repeat_penalty` |
| Extra Body | arbitrary JSON merged into options |

![Ollama Option Nodes](docs/assets/ollama_options.png)

### Multi-turn conversations

`OLLAMA_HISTORY` flows out of Chat Completion as a list of `{"role", "content"}` dicts. Wire it back into the next Chat Completion for multi-turn conversations, or inspect it with **Ollama Debug History** / **Ollama History Length**.

### Upgrading an older workflow

If you saved a workflow before this rename, ComfyUI will report the old node types as missing when you reopen it. Reconnect using this mapping, then re-run — behavior is unchanged, only the names and the client socket type are different:

| Old | New |
|-----|-----|
| `OllamaChatCompletion` | `ChatCompletion` |
| `OllamaModelSelector` | `LLMModelSelector` |
| `OllamaLoadModel` | `LLMLoadModel` |
| `OllamaUnloadModel` | `LLMUnloadModel` |
| `OLLAMA_CLIENT` socket | `LLM_CLIENT` socket |

`OllamaClient` keeps its name — just delete and re-add any downstream node showing as missing, then rewire it to the same `OllamaClient` node.

---

## llama.cpp

A second backend for the same chat/model-management nodes documented above — **LlamaCpp Client** is the only new node; everything else (Chat Completion, LLM Model Selector, LLM Load Model, LLM Unload Model, structured output, multi-turn history) works unchanged, because they don't know or care which backend they're talking to.

### Prerequisite: router mode

`llama-server` needs to be launched in **router mode** — a directory of models, not a single `-m model.gguf`:

```bash
llama-server --models-dir ./models -c 8192
```

This gives `comfydv` live model status (including `loading`/`downloading`, not just loaded/unloaded — a richer picture than Ollama can report) and explicit load/unload, the same way the Ollama nodes already work.

### LlamaCpp Client node

Configure the server address once (default `http://localhost:8080`); every downstream node inherits it automatically — same pattern as Ollama Client, same `LLM_CLIENT` socket.

### Switching an existing workflow from Ollama to llama.cpp

Replace the **Ollama Client** node with an **LlamaCpp Client** node, pointed at your running `llama-server`. Nothing else changes — same Chat Completion node, same Load/Unload nodes, same structured-output behavior. That's the entire point of sharing one `LLM_CLIENT` socket type across backends.

`OllamaClient` keeps its name — just delete and re-add any downstream node showing as missing, then rewire it to the same `OllamaClient` node.
