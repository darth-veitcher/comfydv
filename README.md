# comfydv

A collection of workflow efficiency and quality-of-life nodes built out of necessity for personal ComfyUI use.

## What is this?

`comfydv` fills gaps in ComfyUI's built-in node library: dynamic string formatting, seed-controlled random selection, and graceful workflow interruption. Install it once and connect the nodes like any other — no Python knowledge required.

| Node | What it does |
|------|-------------|
| **Format String** | Formats a string from a Python f-string or Jinja2 template. Detects variables in the template and automatically adds/removes input sockets. |
| **Random Choice** | Accepts any number of typed inputs and outputs one at random, with a configurable seed for reproducibility. |
| **Circuit Breaker** | Halts the current ComfyUI queue run gracefully (raises `InterruptProcessingException`) without crashing the server. |

## Install

1. Clone this repo into your ComfyUI `custom_nodes/` directory:

   ```bash
   cd /path/to/ComfyUI/custom_nodes
   git clone https://github.com/darth-veitcher/comfydv.git
   ```

2. Restart ComfyUI. The nodes appear under the **dv/** category in the node menu.

> **Dependencies** (`jinja2`, `rich`, `colorama`, `termcolor`) are listed in `pyproject.toml`. ComfyUI's Python environment must have them installed — run `pip install jinja2 rich colorama termcolor` inside that environment if they are missing.

## Quickstart

**Format String — simple f-string:**

1. Add a **Format String** node to your workflow.
2. Set `template_type` to `Simple` and enter `Hello {name}` in the template field.
3. A `name` input socket appears automatically — wire it up or type a value.
4. Output 0 (`formatted_string`) contains `Hello <your value>`.

**Random Choice:**

1. Add a **Random Choice** node.
2. Connect any number of inputs (strings, images, conditioning — any type).
3. Set `seed` for reproducibility; leave at `0` for a different pick each run.
4. Output is whichever input was selected.

## Documentation

Full documentation can be found: [darth-veitcher.github.io/comfydv](https://darth-veitcher.github.io/comfydv/stable/)

## String Formatting

The FormatString node provides flexible string formatting with dynamic input/output configuration.

### Python F-String

A simple python f-string dynamically creates the necessary inputs/outputs for the detected keys.

![f-string](docs/assets/fstring.png)

### Jinja 2

Switching to Jinja2 allows you to use more advanced control blocks and other filters/features of that templating language. See [Jinja documentation](https://jinja.palletsprojects.com/en/latest/) for further details.

![jinja2](docs/assets/jinja2.png)

### Output Structure

The node's outputs are organized for maximum reliability and flexibility:

1. **`formatted_string`** (Output 0): The formatted result string - always in position 0
2. **`saved_file_path`** (Output 1): Path to saved state file (if save_path provided) - always in position 1
3. **Variable outputs** (Output 2+): Pass-through values for any variables detected in the template, enabling easy chaining

For example, with template `"Hello {name}, you are {age}"`:

* Output 0: The formatted string (e.g., "Hello Alice, you are 30")
* Output 1: The save file path (or empty string)
* Output 2: The value of `name` (e.g., "Alice")
* Output 3: The value of `age` (e.g., "30")

This structure ensures the primary outputs (`formatted_string` and `saved_file_path`) are always in predictable, fixed positions for reliable workflow connections.

## Random Choice

Ability to take arbitrary length and type of inputs to then output a **choice** with a controllable seed.

![random](docs/assets/random.png)
