"""
Ollama model integration nodes for ComfyUI.

Client configuration, auth headers, model discovery, load/unload, chat
completion, composable inference options, and history utilities.

ADR-004: aiohttp (already in ComfyUI dep tree) for all Ollama HTTP calls.
ADR-005: OllamaClient node is the single source of the host URL (and, per
US7, of any auth headers — every downstream node reaches the same server).
ADR-007: OllamaClient now emits an OllamaProvider (comfydv._llm), the
LLMProvider adapter-pattern boundary shared with future backends. Chat,
model listing, and load/unload nodes are generic (ChatCompletion,
LLMModelSelector, LLMLoadModel, LLMUnloadModel) and delegate to whichever
provider is wired in — see MIGRATION_MAP below for the old Ollama-specific
names these replace. Structured output is now pydantic-ai backed
(comfydv._llm.chat), superseding ADR-006's hand-rolled tool-calling.
"""

import json
import logging
import os
import sys

from comfydv._llm.ollama_provider import OllamaProvider, _fetch_models, _run_async
from comfydv._llm.provider import Message

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Migration mapping (ADR-007) — old Ollama-specific node/socket names to
# their generic replacements, for anyone reconnecting a pre-upgrade
# workflow. See FR-009, specs/007-llm-provider-abstraction/spec.md.
# ---------------------------------------------------------------------------

MIGRATION_MAP: dict[str, str] = {
    "OllamaChatCompletion": "ChatCompletion",
    "OllamaModelSelector": "LLMModelSelector",
    "OllamaLoadModel": "LLMLoadModel",
    "OllamaUnloadModel": "LLMUnloadModel",
    "OLLAMA_CLIENT": "LLM_CLIENT",
}


# ---------------------------------------------------------------------------
# Custom socket types
# ---------------------------------------------------------------------------


class OllamaClientType(str):
    """Typed string carrying the Ollama host URL through the node graph.

    Superseded by ``OllamaProvider`` (comfydv._llm.ollama_provider) as of
    ADR-007 — ``OllamaClient.create_client()`` no longer constructs this.
    Left in place (unreferenced) rather than deleted; removing a class
    nothing references is a separate, lower-risk cleanup outside this
    cutover's scope.
    """

    def __new__(cls, host, headers=None):
        obj = super().__new__(cls, host)
        obj.headers = dict(headers) if headers else {}
        return obj


# ---------------------------------------------------------------------------
# Combo-widget model population
# ---------------------------------------------------------------------------
#
# Narrower than OllamaProvider.list_models() (name-only, no live status) —
# used only to populate COMBO dropdowns at node-definition time and by the
# JS refresh button, neither of which has a constructed provider instance
# to call. _fetch_models/_run_async are the single source of truth,
# imported from comfydv._llm.ollama_provider (ADR-007) rather than
# duplicated here.


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
# OllamaClient
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

    RETURN_TYPES = ("LLM_CLIENT",)
    RETURN_NAMES = ("client",)
    FUNCTION = "create_client"
    CATEGORY = "dv/ollama"

    def create_client(self, host: str, headers: dict | None = None):
        return (OllamaProvider(host, headers),)


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
# LLMModelSelector (replaces OllamaModelSelector — MIGRATION_MAP)
# ---------------------------------------------------------------------------


class LLMModelSelector:
    """Passes a model name through, typed for wiring/validation.

    ``client`` is accepted only for typing/wiring — the COMBO dropdown is
    populated separately (see _load_default_models); this node never calls
    the provider. Behavior-identical to the pre-ADR-007 OllamaModelSelector,
    generalized to accept any LLM_CLIENT-typed provider.
    """

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "client": ("LLM_CLIENT",),
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
# LLMLoadModel / LLMUnloadModel (replace OllamaLoadModel/OllamaUnloadModel)
# ---------------------------------------------------------------------------


class LLMLoadModel:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "client": ("LLM_CLIENT",),
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
        _run_async(client.load_model(model))
        return (model,)


class LLMUnloadModel:
    """Evict a model from VRAM and pass a value through unchanged.

    Wire ``passthrough`` from a downstream node (e.g. the ``response`` output
    of ChatCompletion) so ComfyUI executes this node *after* that node
    completes.  The value is returned unchanged so the rest of the workflow can
    continue using it.
    """

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "client": ("LLM_CLIENT",),
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
        _run_async(client.unload_model(model))
        return (model, passthrough)


# ---------------------------------------------------------------------------
# ChatCompletion (replaces OllamaChatCompletion — MIGRATION_MAP)
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
# Structured output schema helpers — stay here (pure/local, no network
# dependency), shared by ChatCompletion.chat() and the live-preview route.
# The actual structured-output *mechanism* (tool-calling, retry, validation)
# moved to comfydv._llm.chat / pydantic-ai as of ADR-007, superseding
# ADR-006's hand-rolled approach.

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
    ChatCompletion already re-executes every queue run (OUTPUT_NODE=True).

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
    return create_model("StructuredOutput", **fields)


def _coerce_structured_value(value, comfy_type: str):
    if comfy_type == "STRING" and isinstance(value, (list, dict)):
        return json.dumps(value)
    if comfy_type == "STRING" and value is None:
        return ""
    return value


class ChatCompletion:
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
                "client": ("LLM_CLIENT",),
                # Plain STRING so it can receive a wired value from LLMLoadModel
                # (or LLMModelSelector) without needing a separate model_name socket.
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
        message_dicts = list(history)
        if system:
            message_dicts = [{"role": "system", "content": system}] + message_dicts
        message_dicts.append({"role": "user", "content": prompt})
        messages = [Message(**m) for m in message_dicts]
        llm_options = dict(options) if options else None

        # Provider owns transport, caching, and — for structured_output — the
        # tool-calling/retry/validation mechanism (pydantic-ai, ADR-007).
        # ChatCompletion never branches on which concrete provider it got.
        if not structured_output:
            parsed = None
            response_text = _run_async(
                client.chat(
                    effective_model, messages, llm_options, timeout_secs=float(timeout_secs)
                )
            )
        else:
            assert pydantic_model is not None  # structured_output implies this was built
            parsed = _run_async(
                client.chat_structured(
                    effective_model,
                    messages,
                    pydantic_model,
                    llm_options,
                    timeout_secs=float(timeout_secs),
                    max_retries=max_retries,
                )
            )
            response_text = parsed.model_dump_json()

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
# ChatCompletion.RETURN_TYPES/RETURN_NAMES (the same update_outputs()
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
            ChatCompletion.update_outputs(
                unique_id, structured_output and schema is not None, schema
            )

        outputs = [
            {"name": name, "type": otype}
            for name, otype in zip(
                ChatCompletion.RETURN_NAMES, ChatCompletion.RETURN_TYPES
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
