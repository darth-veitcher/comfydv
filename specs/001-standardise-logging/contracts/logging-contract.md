# Developer Logging Contract — comfydv

After this change, the package exposes a standard Python logging hierarchy. ComfyUI users see nothing by default; developers who want traces configure the standard library.

## Logger hierarchy

```
comfydv                        ← root package logger (NullHandler attached)
├── comfydv.format_string      ← FormatString node traces
├── comfydv.random_choice      ← RandomChoice node traces
└── comfydv.circuit_breaker    ← CircuitBreaker node traces
```

All loggers are named via `logging.getLogger(__name__)` — standard Python convention.

## Enabling debug output (developer / ComfyUI startup script)

```python
import logging
logging.getLogger("comfydv").setLevel(logging.DEBUG)
logging.getLogger("comfydv").addHandler(logging.StreamHandler())
```

Or, to target a single node:

```python
logging.getLogger("comfydv.format_string").setLevel(logging.DEBUG)
```

## Log levels by event

| Event | Level | Example message |
|-------|-------|-----------------|
| Template variables extracted | DEBUG | `"FormatString: extracted keys %s"` |
| IS_CHANGED / update_widget call | DEBUG | `"IS_CHANGED: template_type=%s"` |
| Successful format execution | DEBUG | `"FormatString: rendered %d chars"` |
| State saved to disk | INFO | `"FormatString: state saved to %s"` |
| Template syntax error | ERROR | `"Jinja2 template error: %s"` |
| Missing variable (KeyError) | ERROR | `"Missing variable in template: %s"` |
| File save failure | ERROR | `"Failed to save state to %s: %s"` |
| RandomChoice selection | DEBUG | `"RandomChoice: selected index %d"` |
| CircuitBreaker interrupt | DEBUG | `"CircuitBreaker: interrupt triggered"` |
| Module loaded outside ComfyUI | WARNING | `"ComfyUI not detected — node will not function outside ComfyUI"` |

## What a normal ComfyUI run looks like

With default ComfyUI logging (INFO handler on root logger, no comfydv-specific config):

- **Zero output** from comfydv during node execution
- Errors (template failures, save failures) **do** appear because they are logged at ERROR

## Stability guarantee

Logger names (`comfydv`, `comfydv.format_string`, etc.) are stable across patch releases. The set of events logged at each level may expand (new DEBUG lines) but events currently at WARNING/ERROR will not be downgraded without a minor-version bump.
