"""llama.cpp connection node for ComfyUI.

Mirrors comfydv.ollama's OllamaClient exactly (ADR-007's parallel-
implementation pattern) — LlamaCppClient is the only new node this feature
introduces. Every other generic node (ChatCompletion, LLMModelSelector,
LLMLoadModel, LLMUnloadModel) already works with any LLM_CLIENT-typed
provider unchanged.

Deployment prerequisite: llama-server must be launched in router mode
(--models-dir or --models-preset) — see specs/008-llamacpp-integration/quickstart.md.
"""

from comfydv._llm.llamacpp_provider import LlamaCppProvider


class LlamaCppClient:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "host": ("STRING", {"default": "http://localhost:8080"}),
            },
            "optional": {
                "headers": ("OLLAMA_HEADERS",),
            },
        }

    RETURN_TYPES = ("LLM_CLIENT",)
    RETURN_NAMES = ("client",)
    FUNCTION = "create_client"
    CATEGORY = "dv/llamacpp"

    def create_client(self, host: str, headers: dict | None = None):
        return (LlamaCppProvider(host, headers),)
