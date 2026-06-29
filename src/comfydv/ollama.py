"""
Ollama model integration nodes for ComfyUI.

14 nodes: client configuration, model discovery, load/unload, chat completion,
composable inference options, and history utilities.

ADR-004: aiohttp (already in ComfyUI dep tree) for all Ollama HTTP calls.
ADR-005: OllamaClient node is the single source of the host URL.
"""

import asyncio
import json
import logging
import sys

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom socket type
# ---------------------------------------------------------------------------


class OllamaClientType(str):
    """Typed string carrying the Ollama host URL through the node graph."""


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


async def _fetch_models(host: str) -> list[str]:
    """GET {host}/api/tags — return list of model name strings."""
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{host}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                data = await resp.json()
                return [m["name"] for m in data.get("models", [])]
    except Exception as exc:
        logger.warning("Could not fetch Ollama models from %s: %s", host, exc)
        return []


async def _post_json(url: str, payload: dict, *, timeout: float = 120.0) -> dict:
    """POST JSON to url, return parsed response dict."""
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
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


# Static placeholder — avoids a network call at import time (which always fails
# in CI and slows cold-start). The JS refresh button calls /dv/ollama/models
# at runtime to populate the live list.
_DEFAULT_MODELS: list[str] = ["(⟳ click Refresh models)"]


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
            }
        }

    RETURN_TYPES = ("OLLAMA_CLIENT",)
    RETURN_NAMES = ("client",)
    FUNCTION = "create_client"
    CATEGORY = "dv/ollama"

    def create_client(self, host: str):
        return (OllamaClientType(host),)


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
            )
        )
        return (model, passthrough)


# ---------------------------------------------------------------------------
# US4 — OllamaChatCompletion
# ---------------------------------------------------------------------------


class OllamaChatCompletion:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "client": ("OLLAMA_CLIENT",),
                "model": (_DEFAULT_MODELS, {}),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "system": ("STRING", {"multiline": True, "default": ""}),
                "history": ("OLLAMA_HISTORY",),
                "options": ("OLLAMA_OPTIONS",),
                # Wire OllamaLoadModel.model_name here to guarantee load runs
                # before chat and to override the dropdown with the wired value.
                "model_name": ("STRING", {"forceInput": True}),
                "timeout_secs": ("INT", {"default": 300, "min": 30, "max": 3600}),
            },
        }

    RETURN_TYPES = ("STRING", "OLLAMA_HISTORY", "STRING")
    RETURN_NAMES = ("response", "updated_history", "model_name")
    FUNCTION = "chat"
    CATEGORY = "dv/ollama"

    def chat(
        self,
        client,
        model,
        prompt,
        system="",
        history=None,
        options=None,
        model_name=None,
        timeout_secs=300,
    ):
        effective_model = (
            model_name.strip() if model_name and model_name.strip() else model
        )
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
        result = _run_async(
            _post_json(f"{client}/api/chat", payload, timeout=float(timeout_secs))
        )
        response_text = result.get("message", {}).get("content", "")
        updated = list(history)
        updated.append({"role": "user", "content": prompt})
        updated.append({"role": "assistant", "content": response_text})
        return (response_text, updated, effective_model)


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
