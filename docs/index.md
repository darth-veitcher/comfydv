# comfydv

A collection of workflow efficiency and quality-of-life nodes built out of necessity for personal ComfyUI use.

| Node | What it does |
|------|-------------|
| **Format String** | Formats a string from a Python f-string or Jinja2 template. Detects variables in the template and automatically adds/removes input sockets. |
| **Random Choice** | Accepts any number of typed inputs and outputs one at random, with a configurable seed for reproducibility. |
| **Circuit Breaker** | Halts the current ComfyUI queue run gracefully without crashing the server. Wire the `status` toggle to a boolean condition to skip the rest of the queue when a condition isn't met. |

## Install

**Via ComfyUI Manager** (recommended): search for `comfydv` and click Install.

**Manual:**

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/darth-veitcher/comfydv.git
```

Restart ComfyUI. The nodes appear under the **dv/** category in the node menu. The only runtime dependency is `jinja2`, installed automatically via `requirements.txt`.

---

## Format String

Formats text from a Python f-string or Jinja2 template. As you type the template, input sockets appear and disappear automatically — one per variable detected.

### Python f-strings

Type `{variable_name}` and a socket appears. Wire it to any string output in your workflow.

![Format String — f-string mode](assets/fstring.png)

| Output | Content |
|--------|---------|
| `formatted_string` | The rendered result |
| `saved_file_path` | Path written to disk (if `save_path` is set) |
| `<var>` … | Pass-through of each input value, for easy chaining |

### Jinja2 templates

Switch `template_type` to **Jinja2** to unlock filters (`| upper`, `| int`, …), conditionals (`{% if %}…{% endif %}`), and loops.

![Format String — Jinja2 mode](assets/jinja2.png)

Variables detected in `{{ }}` expressions become input sockets exactly as in Simple mode. See the [Jinja2 documentation](https://jinja.palletsprojects.com/en/latest/) for the full filter/test reference.

---

## Random Choice

Connect any number of inputs of the same type. Each run picks one at random. Set `seed` for reproducibility.

![Random Choice](assets/random.png)

- Accepts any ComfyUI type (STRING, IMAGE, CONDITIONING, …)
- Add as many inputs as you like; unused slots are removed automatically when disconnected
- `seed = 0` randomises on every run; any other value locks the selection

---

## Circuit Breaker

Stops the queue gracefully when a condition isn't met — no crash, no error, just a clean halt.

![Circuit Breaker](assets/circuit_breaker.png)

Wire an image (or any trigger) into `trigger` and a boolean into `status`. When `status` is **false** the node raises `InterruptProcessingException`, which tells ComfyUI to stop the current run cleanly. When `status` is **true** the image passes through unchanged.

Typical use: skip an expensive upscale step when a quality-check node says the draft is already good enough.
