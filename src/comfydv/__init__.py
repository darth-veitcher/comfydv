import logging

from .circuit_breaker import CircuitBreaker
from .format_string import FormatString
from .ollama import (
    OllamaClient,
    OllamaChatCompletion,
    OllamaDebugHistory,
    OllamaHistoryLength,
    OllamaLoadModel,
    OllamaModelSelector,
    OllamaOptionExtraBody,
    OllamaOptionMaxTokens,
    OllamaOptionRepeatPenalty,
    OllamaOptionSeed,
    OllamaOptionTemperature,
    OllamaOptionTopK,
    OllamaOptionTopP,
    OllamaUnloadModel,
)
from .random_choice import RandomChoice

logging.getLogger(__name__).addHandler(logging.NullHandler())

# A dictionary that contains all nodes you want to export with their names
# NOTE: names should be globally unique
NODE_CLASS_MAPPINGS = {
    "RandomChoice": RandomChoice,
    "CircuitBreaker": CircuitBreaker,
    "FormatString": FormatString,
    # Ollama nodes
    "OllamaClient": OllamaClient,
    "OllamaModelSelector": OllamaModelSelector,
    "OllamaLoadModel": OllamaLoadModel,
    "OllamaUnloadModel": OllamaUnloadModel,
    "OllamaChatCompletion": OllamaChatCompletion,
    "OllamaOptionTemperature": OllamaOptionTemperature,
    "OllamaOptionSeed": OllamaOptionSeed,
    "OllamaOptionMaxTokens": OllamaOptionMaxTokens,
    "OllamaOptionTopP": OllamaOptionTopP,
    "OllamaOptionTopK": OllamaOptionTopK,
    "OllamaOptionRepeatPenalty": OllamaOptionRepeatPenalty,
    "OllamaOptionExtraBody": OllamaOptionExtraBody,
    "OllamaDebugHistory": OllamaDebugHistory,
    "OllamaHistoryLength": OllamaHistoryLength,
}

# A dictionary that contains the friendly/humanly readable titles for the nodes
NODE_DISPLAY_NAME_MAPPINGS = {
    "RandomChoice": "Random Choice",
    "CircuitBreaker": "Circuit Breaker",
    "FormatString": "Format String (Python f-strings)",
    # Ollama nodes
    "OllamaClient": "Ollama Client",
    "OllamaModelSelector": "Ollama Model Selector",
    "OllamaLoadModel": "Ollama Load Model",
    "OllamaUnloadModel": "Ollama Unload Model",
    "OllamaChatCompletion": "Ollama Chat Completion",
    "OllamaOptionTemperature": "Ollama Option — Temperature",
    "OllamaOptionSeed": "Ollama Option — Seed",
    "OllamaOptionMaxTokens": "Ollama Option — Max Tokens",
    "OllamaOptionTopP": "Ollama Option — Top P",
    "OllamaOptionTopK": "Ollama Option — Top K",
    "OllamaOptionRepeatPenalty": "Ollama Option — Repeat Penalty",
    "OllamaOptionExtraBody": "Ollama Option — Extra Body",
    "OllamaDebugHistory": "Ollama Debug History",
    "OllamaHistoryLength": "Ollama History Length",
}

WEB_DIRECTORY = "../js"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
