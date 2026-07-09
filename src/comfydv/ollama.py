"""
Ollama model integration nodes for ComfyUI.

17 nodes: client configuration, auth headers, model discovery, load/unload,
chat completion, composable inference options, and history utilities.

ADR-004: aiohttp (already in ComfyUI dep tree) for all Ollama HTTP calls.
ADR-005: OllamaClient node is the single source of the host URL (and, per
US7, of any auth headers — every downstream node reaches the same server).
ADR-006: structured_output uses Ollama's OpenAI-compatible tool-calling
endpoint + a dynamically-built pydantic model for validation, not
pydantic-ai — still plain aiohttp, no new HTTP client.
"""

import asyncio
import json
import logging
import os
import sys
import threading
import time

from pydantic import ValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Local response cache
# ---------------------------------------------------------------------------
#
# OllamaChatCompletion is OUTPUT_NODE=True (needed for inline display), which
# means ComfyUI re-executes it on every queue run even when none of its
# inputs changed — unlike normal nodes, it isn't skipped by ComfyUI's own
# input-hash cache. This cache absorbs those redundant round-trips: identical
# (client, headers, model, messages, options) reuse the prior response
# instead of re-querying Ollama. Model discovery gets the same treatment
# (many nodes independently query /api/tags on graph load) but with a short
# TTL so a newly-pulled model still surfaces after a refresh.


class _TTLLRUCache:
    """Bounded cache, LRU-evicted, with an optional per-entry TTL."""

    def __init__(self, maxsize: int, ttl_seconds: float | None = None):
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._data: dict = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None, False
            expires_at, value = entry
            if self.ttl_seconds is not None and time.monotonic() > expires_at:
                del self._data[key]
                return None, False
            # Re-insert to mark as most-recently-used (dicts preserve insertion order).
            del self._data[key]
            self._data[key] = (expires_at, value)
            return value, True

    def set(self, key, value):
        with self._lock:
            expires_at = (
                time.monotonic() + self.ttl_seconds
                if self.ttl_seconds is not None
                else float("inf")
            )
            self._data.pop(key, None)
            self._data[key] = (expires_at, value)
            while len(self._data) > self.maxsize:
                oldest_key = next(iter(self._data))
                del self._data[oldest_key]

    def clear(self):
        with self._lock:
            self._data.clear()


def _cache_key(*parts) -> str:
    """Deterministic, hashable key from arbitrary JSON-serializable parts."""
    return json.dumps(parts, sort_keys=True, default=str)


_MODEL_LIST_CACHE = _TTLLRUCache(maxsize=32, ttl_seconds=20.0)
_CHAT_RESPONSE_CACHE = _TTLLRUCache(maxsize=64, ttl_seconds=None)


# ---------------------------------------------------------------------------
# Custom socket types
# ---------------------------------------------------------------------------


class OllamaClientType(str):
    """Typed string carrying the Ollama host URL through the node graph.

    Also carries an optional ``.headers`` dict (US7 — basic auth / bearer
    tokens for Ollama servers behind a reverse proxy). Since this is a plain
    ``str`` subclass, every existing ``f"{client}/api/..."`` call site keeps
    working unchanged; only code that wants auth reads ``.headers``.
    """

    def __new__(cls, host, headers=None):
        obj = super().__new__(cls, host)
        obj.headers = dict(headers) if headers else {}
        return obj


def _client_headers(client) -> dict | None:
    """Extract auth headers stashed on an OllamaClientType, if any."""
    headers = getattr(client, "headers", None)
    return dict(headers) if headers else None


# ---------------------------------------------------------------------------
# Async infrastructure
# ---------------------------------------------------------------------------


def _run_async(coro):
    """Run an async coroutine synchronously, safe inside a running event loop."""
    try:
        asyncio.get_running_loop()
        # Called from within a running loop (e.g. ComfyUI's async executor).
        # Spin up a worker thread with its own loop to avoid "loop already running".
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


async def _fetch_models(host: str, headers: dict | None = None) -> list[str]:
    """GET {host}/api/tags — return list of model name strings.

    Cached for _MODEL_LIST_CACHE.ttl_seconds per (host, headers) pair — node
    creation, the Refresh button, and startup all otherwise re-issue this
    same request in quick succession.
    """
    cache_key = _cache_key("models", host, headers or {})
    cached, hit = _MODEL_LIST_CACHE.get(cache_key)
    if hit:
        return cached

    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{host}/api/tags",
                headers=headers or None,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                data = await resp.json()
                models = [m["name"] for m in data.get("models", [])]
    except Exception as exc:
        logger.warning("Could not fetch Ollama models from %s: %s", host, exc)
        return []

    if models:
        _MODEL_LIST_CACHE.set(cache_key, models)
    return models


async def _post_json(
    url: str,
    payload: dict,
    *,
    timeout: float = 120.0,
    headers: dict | None = None,
) -> dict:
    """POST JSON to url, return parsed response dict."""
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers or None,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    raise RuntimeError(
                        f"Ollama returned HTTP {resp.status} for {url}: {body[:300]}"
                    )
                return await resp.json()
    except aiohttp.ClientConnectionError as exc:
        raise RuntimeError(f"Cannot reach Ollama at {url}: {exc}") from exc


def _load_default_models() -> list[str]:
    """Fetch the installed model list at server start-up.

    Tries OLLAMA_HOST env var first (set in docker-compose for host.docker.internal),
    then falls back to localhost.  Returns a one-element placeholder list only when
    Ollama is genuinely unreachable so that COMBO validation doesn't reject saved
    workflow values.
    """
    candidates = []
    env_host = os.environ.get("OLLAMA_HOST", "").strip()
    if env_host:
        candidates.append(env_host)
    candidates.append("http://host.docker.internal:11434")
    candidates.append("http://localhost:11434")

    for host in candidates:
        models = _run_async(_fetch_models(host))
        if models:
            logger.info("Ollama models loaded from %s: %s", host, models)
            return models

    logger.warning(
        "Could not reach Ollama at any candidate host %s — "
        "model dropdowns will be empty until a Refresh is clicked.",
        candidates,
    )
    return ["(start Ollama — click ⟳ Refresh)"]


_DEFAULT_MODELS: list[str] = _load_default_models()


# ---------------------------------------------------------------------------
# ComfyUI server route (load-guarded)
# ---------------------------------------------------------------------------

if "comfy" in sys.modules:
    from server import PromptServer

    @PromptServer.instance.routes.get("/dv/ollama/models")
    async def _models_endpoint(request):
        from aiohttp import web

        host = request.rel_url.query.get("host", "http://localhost:11434")
        models = await _fetch_models(host)
        if models:
            return web.json_response({"models": models})
        return web.json_response({"error": f"No models found at {host}"}, status=503)

else:
    logger.warning(
        "ComfyUI not detected — /dv/ollama/models route will not be registered."
    )


# ---------------------------------------------------------------------------
# US1 — OllamaClient
# ---------------------------------------------------------------------------


class OllamaClient:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "host": ("STRING", {"default": "http://localhost:11434"}),
            },
            "optional": {
                "headers": ("OLLAMA_HEADERS",),
            },
        }

    RETURN_TYPES = ("OLLAMA_CLIENT",)
    RETURN_NAMES = ("client",)
    FUNCTION = "create_client"
    CATEGORY = "dv/ollama"

    def create_client(self, host: str, headers: dict | None = None):
        return (OllamaClientType(host, headers),)


# ---------------------------------------------------------------------------
# US7 — Composable auth headers
# ---------------------------------------------------------------------------


def _merge_header(headers, name, value):
    result = dict(headers) if headers else {}
    result[name] = value
    return result


class OllamaHeaderBasicAuth:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "username": ("STRING", {"default": ""}),
                "password": ("STRING", {"default": ""}),
            },
            "optional": {"headers": ("OLLAMA_HEADERS",)},
        }

    RETURN_TYPES = ("OLLAMA_HEADERS",)
    RETURN_NAMES = ("headers",)
    FUNCTION = "set_basic_auth"
    CATEGORY = "dv/ollama/headers"

    def set_basic_auth(self, username, password, headers=None):
        import base64

        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        return (_merge_header(headers, "Authorization", f"Basic {token}"),)


class OllamaHeaderBearerToken:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "token": ("STRING", {"default": ""}),
            },
            "optional": {"headers": ("OLLAMA_HEADERS",)},
        }

    RETURN_TYPES = ("OLLAMA_HEADERS",)
    RETURN_NAMES = ("headers",)
    FUNCTION = "set_bearer_token"
    CATEGORY = "dv/ollama/headers"

    def set_bearer_token(self, token, headers=None):
        return (_merge_header(headers, "Authorization", f"Bearer {token}"),)


class OllamaHeaderCustom:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "name": ("STRING", {"default": ""}),
                "value": ("STRING", {"default": ""}),
            },
            "optional": {"headers": ("OLLAMA_HEADERS",)},
        }

    RETURN_TYPES = ("OLLAMA_HEADERS",)
    RETURN_NAMES = ("headers",)
    FUNCTION = "set_custom_header"
    CATEGORY = "dv/ollama/headers"

    def set_custom_header(self, name, value, headers=None):
        if not name.strip():
            raise ValueError("header name cannot be empty")
        return (_merge_header(headers, name, value),)


# ---------------------------------------------------------------------------
# US2 — OllamaModelSelector
# ---------------------------------------------------------------------------


class OllamaModelSelector:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "client": ("OLLAMA_CLIENT",),
                "model": (_DEFAULT_MODELS, {}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("model_name",)
    FUNCTION = "select_model"
    CATEGORY = "dv/ollama"

    def select_model(self, client, model: str):
        return (model,)


# ---------------------------------------------------------------------------
# US3 — OllamaLoadModel / OllamaUnloadModel
# ---------------------------------------------------------------------------


class OllamaLoadModel:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "client": ("OLLAMA_CLIENT",),
                "model": (_DEFAULT_MODELS, {}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("model_name",)
    FUNCTION = "load_model"
    CATEGORY = "dv/ollama"

    def load_model(self, client, model: str):
        if not model.strip():
            raise ValueError("model name cannot be empty")
        _run_async(
            _post_json(
                f"{client}/api/generate",
                {"model": model, "keep_alive": -1, "stream": False},
                timeout=300.0,
                headers=_client_headers(client),
            )
        )
        return (model,)


class OllamaUnloadModel:
    """Evict a model from VRAM and pass a value through unchanged.

    Wire ``passthrough`` from a downstream node (e.g. the ``response`` output
    of OllamaChatCompletion) so ComfyUI executes this node *after* that node
    completes.  The value is returned unchanged so the rest of the workflow can
    continue using it.
    """

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "client": ("OLLAMA_CLIENT",),
                "model": ("STRING", {"forceInput": True}),
            },
            "optional": {
                "passthrough": ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("model_name", "passthrough")
    FUNCTION = "unload_model"
    CATEGORY = "dv/ollama"

    def unload_model(self, client, model: str, passthrough: str = ""):
        if not model.strip():
            raise ValueError("model name cannot be empty")
        _run_async(
            _post_json(
                f"{client}/api/generate",
                {"model": model, "keep_alive": 0, "stream": False},
                timeout=30.0,
                headers=_client_headers(client),
            )
        )
        return (model, passthrough)


# ---------------------------------------------------------------------------
# US4 — OllamaChatCompletion
# ---------------------------------------------------------------------------


def _history_preview(messages: list[dict]) -> str:
    """Compact multi-turn summary shown below the response in the node body."""
    lines = []
    for m in messages[-6:]:
        prefix = "▶" if m["role"] == "user" else "·"
        snippet = m["content"][:100]
        if len(m["content"]) > 100:
            snippet += "…"
        lines.append(f"{prefix} {snippet}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Structured output — Ollama's OpenAI-compatible /v1/chat/completions
# tool-calling, with a single forced tool matching output_schema
# ---------------------------------------------------------------------------
#
# ADR-006: forces the model to emit its answer as a single tool call whose
# arguments match output_schema, instead of relying on prompt wording —
# fixes commentary, code-fence wrapping, and blank output at the source.
# Ollama's native /api/chat "format" (JSON-Schema-constrained decoding) was
# tried first but proved unreliable against at least one real model in
# testing (a modified-tokenizer quantization silently ignored the schema
# rather than erroring); tool-calling relies on the model's own trained
# function-calling behavior instead of grammar-to-token mapping, and is
# still reached over the existing aiohttp-based _post_json — no new HTTP
# client. pydantic is used purely to dynamically build a validation model
# from the user's schema, not as an HTTP client.

_JSON_SCHEMA_TO_PY_TYPE: dict = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}
_JSON_SCHEMA_TO_COMFY_TYPE: dict = {
    "string": "STRING",
    "integer": "INT",
    "number": "FLOAT",
    "boolean": "BOOLEAN",
    "array": "STRING",
    "object": "STRING",
}
_DEFAULT_OUTPUT_SCHEMA = (
    '{"type": "object", "properties": '
    '{"output": {"type": "string"}}, "required": ["output"]}'
)


def _parse_output_schema(output_schema: str) -> dict:
    """Parse+validate output_schema JSON, fail fast before any network call."""
    try:
        schema = json.loads(output_schema)
    except json.JSONDecodeError as exc:
        raise ValueError(f"output_schema is not valid JSON: {exc}") from exc
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ValueError(
            'output_schema must be a JSON Schema object with "type": "object" '
            'at the root, e.g. {"type": "object", "properties": {...}}'
        )
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise ValueError(
            "output_schema.properties must be a non-empty object — "
            "structured_output requires at least one field to extract"
        )
    return schema


def _comfy_types_for_schema(schema: dict) -> tuple:
    return tuple(
        _JSON_SCHEMA_TO_COMFY_TYPE.get(prop.get("type"), "STRING")
        for prop in schema["properties"].values()
    )


def _build_structured_model(schema: dict):
    """Dynamically build a pydantic BaseModel from schema properties/required.

    Rebuilt every call — create_model() on a handful of fields is cheap, and
    OllamaChatCompletion already re-executes every queue run (OUTPUT_NODE=True).

    Required *string* fields get `min_length=1`: JSON Schema's "required"
    only checks presence, so a model could satisfy it with `""` — which is
    exactly the "blank output" problem this feature exists to eliminate. An
    empty required string now fails validation and triggers a retry like any
    other malformed response, rather than silently passing through.
    """
    from pydantic import Field, create_model

    required = set(schema.get("required", []))
    fields = {}
    for name, prop in schema["properties"].items():
        py_type = _JSON_SCHEMA_TO_PY_TYPE.get(prop.get("type"), str)
        if name not in required:
            fields[name] = (py_type, None)
        elif py_type is str:
            fields[name] = (py_type, Field(..., min_length=1))
        else:
            fields[name] = (py_type, ...)
    return create_model("OllamaStructuredOutput", **fields)


def _coerce_structured_value(value, comfy_type: str):
    if comfy_type == "STRING" and isinstance(value, (list, dict)):
        return json.dumps(value)
    if comfy_type == "STRING" and value is None:
        return ""
    return value


_STRUCTURED_TOOL_NAME = "emit_structured_output"


def _build_tool_call_payload(schema: dict) -> tuple:
    """tools/tool_choice extras forcing a single call matching schema."""
    tools = [
        {
            "type": "function",
            "function": {
                "name": _STRUCTURED_TOOL_NAME,
                "description": "Emit the result matching the required schema.",
                "parameters": schema,
            },
        }
    ]
    tool_choice = {"type": "function", "function": {"name": _STRUCTURED_TOOL_NAME}}
    return tools, tool_choice


def _extract_tool_call_arguments(result: dict) -> str:
    """Pull the forced tool call's arguments JSON string out of an OpenAI-
    compatible /v1/chat/completions response. Empty string (which will fail
    pydantic validation and trigger a retry) if the model didn't call the
    tool at all — this happens on occasion even with tool_choice forcing it.
    """
    choices = result.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message", {})
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        return ""
    return tool_calls[0].get("function", {}).get("arguments", "") or ""


class OllamaChatCompletion:
    OUTPUT_NODE = True

    _BASE_RETURN_TYPES = ("STRING", "OLLAMA_HISTORY", "STRING")
    _BASE_RETURN_NAMES = ("response", "updated_history", "model_name")

    # Per-node-instance structured-output config, keyed by unique_id — same
    # pattern as FormatString.node_configs.
    node_configs: dict = {}

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "client": ("OLLAMA_CLIENT",),
                # Plain STRING so it can receive a wired value from OllamaLoadModel
                # (or OllamaModelSelector) without needing a separate model_name socket.
                "model": ("STRING", {"default": ""}),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "system": ("STRING", {"multiline": True, "default": ""}),
                "history": ("OLLAMA_HISTORY",),
                "options": ("OLLAMA_OPTIONS",),
                "timeout_secs": ("INT", {"default": 300, "min": 30, "max": 3600}),
                "structured_output": ("BOOLEAN", {"default": False}),
                "output_schema": (
                    "STRING",
                    {"multiline": True, "default": _DEFAULT_OUTPUT_SCHEMA},
                ),
                "max_retries": ("INT", {"default": 2, "min": 0, "max": 5}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = _BASE_RETURN_TYPES
    RETURN_NAMES = _BASE_RETURN_NAMES
    FUNCTION = "chat"
    CATEGORY = "dv/ollama"

    @classmethod
    def update_outputs(
        cls, unique_id: str, structured_output: bool, schema: dict | None
    ) -> None:
        """Mutate class-level RETURN_TYPES/RETURN_NAMES for structured_output mode.

        Same class-level-shared-state pattern (and limitation) as
        FormatString.update_widget: RETURN_TYPES/RETURN_NAMES are shared
        across all instances of this node type in a graph, so the very first
        execution after toggling structured_output or editing output_schema
        may show stale downstream socket typing until it runs once.
        """
        cls.node_configs[unique_id] = {
            "structured_output": structured_output,
            "schema": schema,
        }
        if not structured_output or not schema:
            cls.RETURN_TYPES = cls._BASE_RETURN_TYPES
            cls.RETURN_NAMES = cls._BASE_RETURN_NAMES
            return
        names = tuple(schema["properties"].keys())
        cls.RETURN_TYPES = cls._BASE_RETURN_TYPES + _comfy_types_for_schema(schema)
        cls.RETURN_NAMES = cls._BASE_RETURN_NAMES + names

    def chat(
        self,
        client,
        model,
        prompt,
        system="",
        history=None,
        options=None,
        timeout_secs=300,
        structured_output=False,
        output_schema=_DEFAULT_OUTPUT_SCHEMA,
        max_retries=2,
        unique_id="",
    ):
        effective_model = model.strip()
        if not effective_model:
            raise ValueError("model cannot be empty — type a model name or wire one in")

        schema = None
        pydantic_model = None
        if structured_output:
            schema = _parse_output_schema(output_schema)  # fail fast, no network call
            pydantic_model = _build_structured_model(schema)

        if unique_id:
            type(self).update_outputs(unique_id, structured_output, schema)

        if history is None:
            history = []
        messages = list(history)
        if system:
            messages = [{"role": "system", "content": system}] + messages
        messages.append({"role": "user", "content": prompt})
        payload: dict = {
            "model": effective_model,
            "messages": messages,
            "stream": False,
        }
        if options:
            payload["options"] = options
        if structured_output:
            # ADR-006: OpenAI-compatible tool-calling, not native /api/chat
            # "format" — forces a single call whose arguments match schema.
            assert schema is not None  # structured_output implies this was parsed
            tools, tool_choice = _build_tool_call_payload(schema)
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        headers = _client_headers(client)
        cache_key = _cache_key(
            "chat",
            client,
            headers or {},
            effective_model,
            messages,
            options or {},
            schema or {},
        )
        cached, hit = _CHAT_RESPONSE_CACHE.get(cache_key)
        url = (
            f"{client}/v1/chat/completions"
            if structured_output
            else f"{client}/api/chat"
        )

        parsed = None
        if not structured_output:
            # Unchanged from pre-structured-output behavior.
            if hit:
                response_text = cached
            else:
                result = _run_async(
                    _post_json(
                        url, payload, timeout=float(timeout_secs), headers=headers
                    )
                )
                response_text = result.get("message", {}).get("content", "")
                _CHAT_RESPONSE_CACHE.set(cache_key, response_text)
        elif hit:
            # schema is part of the cache key, so a hit was necessarily
            # validated against this exact schema when it was written —
            # re-parsing here is guaranteed-successful deserialization, not
            # a fallible re-check.
            assert (
                pydantic_model is not None
            )  # structured_output implies this was built
            response_text = cached
            parsed = pydantic_model.model_validate_json(response_text)
        else:
            assert (
                pydantic_model is not None
            )  # structured_output implies this was built
            total_attempts = max(0, min(int(max_retries), 5)) + 1
            response_text = None
            last_invalid_text = ""
            last_error = None
            for _attempt in range(1, total_attempts + 1):
                result = _run_async(
                    _post_json(
                        url, payload, timeout=float(timeout_secs), headers=headers
                    )
                )
                candidate = _extract_tool_call_arguments(result)
                try:
                    parsed = pydantic_model.model_validate_json(candidate)
                    response_text = candidate
                    _CHAT_RESPONSE_CACHE.set(cache_key, response_text)
                    break
                except ValidationError as exc:
                    last_invalid_text = candidate
                    last_error = exc
            else:
                raise RuntimeError(
                    f"OllamaChatCompletion: structured_output response failed "
                    f"validation against output_schema after {total_attempts} "
                    f"attempt(s) (model={effective_model!r}). Last error: "
                    f"{last_error}. Last response (truncated): "
                    f"{last_invalid_text[:300]!r}"
                )

        updated = list(history)
        updated.append({"role": "user", "content": prompt})
        updated.append({"role": "assistant", "content": response_text})
        n = len(updated)
        ui_text = (
            f"{response_text}\n\n── History: {n} message(s) ──\n{_history_preview(updated)}"
            if n > 2
            else response_text
        )

        result_tuple = (response_text, updated, effective_model)
        if structured_output:
            assert schema is not None  # structured_output implies this was parsed
            comfy_types = _comfy_types_for_schema(schema)
            extra = tuple(
                _coerce_structured_value(getattr(parsed, name), ctype)
                for name, ctype in zip(schema["properties"].keys(), comfy_types)
            )
            result_tuple += extra

        return {
            "ui": {"text": [ui_text]},
            "result": result_tuple,
        }


# ---------------------------------------------------------------------------
# ComfyUI server route — live structured-output socket preview
# ---------------------------------------------------------------------------
#
# Mirrors FormatString's /update_format_string_node route: as the user edits
# structured_output/output_schema, the frontend posts here to recompute
# OllamaChatCompletion.RETURN_TYPES/RETURN_NAMES (the same update_outputs()
# path chat() uses at execution time) and get back the current output list,
# so dynamic sockets appear on the node immediately — no need to run the
# graph first. No network call to Ollama; schema parsing is pure/local.

if "comfy" in sys.modules:
    # PromptServer already imported at module scope by the /dv/ollama/models
    # route registration above.
    @PromptServer.instance.routes.post("/dv/ollama/update_structured_outputs")
    async def _update_structured_outputs_endpoint(request):
        from aiohttp import web

        data = await request.json()
        unique_id = str(data.get("unique_id", ""))
        structured_output = bool(data.get("structured_output", False))
        output_schema = data.get("output_schema", "")

        schema = None
        if structured_output:
            try:
                schema = _parse_output_schema(output_schema)
            except ValueError:
                # Invalid/incomplete JSON while the user is still typing —
                # fall back to the base (non-structured) outputs rather than
                # erroring the request.
                schema = None

        if unique_id:
            OllamaChatCompletion.update_outputs(
                unique_id, structured_output and schema is not None, schema
            )

        outputs = [
            {"name": name, "type": otype}
            for name, otype in zip(
                OllamaChatCompletion.RETURN_NAMES, OllamaChatCompletion.RETURN_TYPES
            )
        ]
        return web.json_response({"outputs": outputs})

else:
    logger.warning(
        "ComfyUI not detected — /dv/ollama/update_structured_outputs route "
        "will not be registered."
    )


# ---------------------------------------------------------------------------
# US5 — Composable option nodes
# ---------------------------------------------------------------------------


def _merge_option(options, key, value):
    result = dict(options) if options else {}
    result[key] = value
    return result


class OllamaOptionTemperature:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "temperature": (
                    "FLOAT",
                    {"default": 0.8, "min": 0.0, "max": 2.0, "step": 0.01},
                ),
            },
            "optional": {"options": ("OLLAMA_OPTIONS",)},
        }

    RETURN_TYPES = ("OLLAMA_OPTIONS",)
    RETURN_NAMES = ("options",)
    FUNCTION = "set_temperature"
    CATEGORY = "dv/ollama/options"

    def set_temperature(self, temperature, options=None):
        return (_merge_option(options, "temperature", temperature),)


class OllamaOptionSeed:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF}),
            },
            "optional": {"options": ("OLLAMA_OPTIONS",)},
        }

    RETURN_TYPES = ("OLLAMA_OPTIONS",)
    RETURN_NAMES = ("options",)
    FUNCTION = "set_seed"
    CATEGORY = "dv/ollama/options"

    def set_seed(self, seed, options=None):
        return (_merge_option(options, "seed", seed),)


class OllamaOptionMaxTokens:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "max_tokens": ("INT", {"default": 512, "min": 1, "max": 131072}),
            },
            "optional": {"options": ("OLLAMA_OPTIONS",)},
        }

    RETURN_TYPES = ("OLLAMA_OPTIONS",)
    RETURN_NAMES = ("options",)
    FUNCTION = "set_max_tokens"
    CATEGORY = "dv/ollama/options"

    def set_max_tokens(self, max_tokens, options=None):
        return (_merge_option(options, "num_predict", max_tokens),)


class OllamaOptionTopP:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "top_p": (
                    "FLOAT",
                    {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
            },
            "optional": {"options": ("OLLAMA_OPTIONS",)},
        }

    RETURN_TYPES = ("OLLAMA_OPTIONS",)
    RETURN_NAMES = ("options",)
    FUNCTION = "set_top_p"
    CATEGORY = "dv/ollama/options"

    def set_top_p(self, top_p, options=None):
        return (_merge_option(options, "top_p", top_p),)


class OllamaOptionTopK:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "top_k": ("INT", {"default": 40, "min": 0, "max": 100}),
            },
            "optional": {"options": ("OLLAMA_OPTIONS",)},
        }

    RETURN_TYPES = ("OLLAMA_OPTIONS",)
    RETURN_NAMES = ("options",)
    FUNCTION = "set_top_k"
    CATEGORY = "dv/ollama/options"

    def set_top_k(self, top_k, options=None):
        return (_merge_option(options, "top_k", top_k),)


class OllamaOptionRepeatPenalty:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "repeat_penalty": (
                    "FLOAT",
                    {"default": 1.1, "min": 0.0, "max": 2.0, "step": 0.01},
                ),
            },
            "optional": {"options": ("OLLAMA_OPTIONS",)},
        }

    RETURN_TYPES = ("OLLAMA_OPTIONS",)
    RETURN_NAMES = ("options",)
    FUNCTION = "set_repeat_penalty"
    CATEGORY = "dv/ollama/options"

    def set_repeat_penalty(self, repeat_penalty, options=None):
        return (_merge_option(options, "repeat_penalty", repeat_penalty),)


class OllamaOptionExtraBody:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "extra_body_json": ("STRING", {"multiline": True, "default": "{}"}),
            },
            "optional": {"options": ("OLLAMA_OPTIONS",)},
        }

    RETURN_TYPES = ("OLLAMA_OPTIONS",)
    RETURN_NAMES = ("options",)
    FUNCTION = "set_extra_body"
    CATEGORY = "dv/ollama/options"

    def set_extra_body(self, extra_body_json, options=None):
        try:
            extra = json.loads(extra_body_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"extra_body_json is not valid JSON: {exc}") from exc
        result = dict(options) if options else {}
        result.update(extra)
        return (result,)


# ---------------------------------------------------------------------------
# US6 — History utilities
# ---------------------------------------------------------------------------


class OllamaDebugHistory:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"history": ("OLLAMA_HISTORY",)}}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("debug_string",)
    FUNCTION = "debug"
    CATEGORY = "dv/ollama"

    def debug(self, history):
        return (json.dumps(history, indent=2),)


class OllamaHistoryLength:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"history": ("OLLAMA_HISTORY",)}}

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("length",)
    FUNCTION = "length"
    CATEGORY = "dv/ollama"

    def length(self, history):
        return (len(history),)
