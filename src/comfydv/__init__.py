import logging

from .circuit_breaker import CircuitBreaker
from .format_string import FormatString
from .llamacpp import LlamaCppClient
from .ollama import (
    ChatCompletion,
    LLMLoadModel,
    LLMModelSelector,
    LLMUnloadModel,
    OllamaClient,
    OllamaDebugHistory,
    OllamaHeaderBasicAuth,
    OllamaHeaderBearerToken,
    OllamaHeaderCustom,
    OllamaHistoryLength,
    OllamaOptionExtraBody,
    OllamaOptionMaxTokens,
    OllamaOptionRepeatPenalty,
    OllamaOptionSeed,
    OllamaOptionTemperature,
    OllamaOptionTopK,
    OllamaOptionTopP,
)
from .random_choice import RandomChoice

logging.getLogger(__name__).addHandler(logging.NullHandler())

# A dictionary that contains all nodes you want to export with their names
# NOTE: names should be globally unique
NODE_CLASS_MAPPINGS = {
    "RandomChoice": RandomChoice,
    "CircuitBreaker": CircuitBreaker,
    "FormatString": FormatString,
    # LLM nodes (generic, ADR-007) — see comfydv.ollama.MIGRATION_MAP for
    # the pre-cutover Ollama-specific names these replace
    "OllamaClient": OllamaClient,
    "LlamaCppClient": LlamaCppClient,
    "LLMModelSelector": LLMModelSelector,
    "LLMLoadModel": LLMLoadModel,
    "LLMUnloadModel": LLMUnloadModel,
    "ChatCompletion": ChatCompletion,
    "OllamaOptionTemperature": OllamaOptionTemperature,
    "OllamaOptionSeed": OllamaOptionSeed,
    "OllamaOptionMaxTokens": OllamaOptionMaxTokens,
    "OllamaOptionTopP": OllamaOptionTopP,
    "OllamaOptionTopK": OllamaOptionTopK,
    "OllamaOptionRepeatPenalty": OllamaOptionRepeatPenalty,
    "OllamaOptionExtraBody": OllamaOptionExtraBody,
    "OllamaDebugHistory": OllamaDebugHistory,
    "OllamaHistoryLength": OllamaHistoryLength,
    "OllamaHeaderBasicAuth": OllamaHeaderBasicAuth,
    "OllamaHeaderBearerToken": OllamaHeaderBearerToken,
    "OllamaHeaderCustom": OllamaHeaderCustom,
}

# A dictionary that contains the friendly/humanly readable titles for the nodes
NODE_DISPLAY_NAME_MAPPINGS = {
    "RandomChoice": "Random Choice",
    "CircuitBreaker": "Circuit Breaker",
    "FormatString": "Format String (Python f-strings)",
    # LLM nodes (generic, ADR-007)
    "OllamaClient": "Ollama Client",
    "LlamaCppClient": "LlamaCpp Client",
    "LLMModelSelector": "LLM Model Selector",
    "LLMLoadModel": "LLM Load Model",
    "LLMUnloadModel": "LLM Unload Model",
    "ChatCompletion": "Chat Completion",
    "OllamaOptionTemperature": "Ollama Option — Temperature",
    "OllamaOptionSeed": "Ollama Option — Seed",
    "OllamaOptionMaxTokens": "Ollama Option — Max Tokens",
    "OllamaOptionTopP": "Ollama Option — Top P",
    "OllamaOptionTopK": "Ollama Option — Top K",
    "OllamaOptionRepeatPenalty": "Ollama Option — Repeat Penalty",
    "OllamaOptionExtraBody": "Ollama Option — Extra Body",
    "OllamaDebugHistory": "Ollama Debug History",
    "OllamaHistoryLength": "Ollama History Length",
    "OllamaHeaderBasicAuth": "Ollama Header — Basic Auth",
    "OllamaHeaderBearerToken": "Ollama Header — Bearer Token",
    "OllamaHeaderCustom": "Ollama Header — Custom",
}

WEB_DIRECTORY = "../js"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
