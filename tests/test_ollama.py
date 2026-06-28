"""
Tests for comfydv.ollama — 14-node Ollama integration.

Test layers:
  Unit (no marker)      — pure Python, no live services
  Integration (-m integration) — requires live Ollama at localhost:11434
  System (-m system)    — requires full docker-compose harness

BDD coverage:
  features/us1_ollama_connection.feature
  features/us2_model_selection.feature
  features/us3_model_lifecycle.feature
  features/us4_chat_completion.feature
  features/us5_composable_options.feature
  features/us6_history_inspection.feature
"""

# ---------------------------------------------------------------------------
# Lazy imports — ollama.py doesn't exist until Phase 3 (T011).
# Uncomment as each task lands:
#
# from comfydv.ollama import (
#     OllamaClientType,
#     OllamaClient,
#     OllamaModelSelector,
#     OllamaLoadModel,
#     OllamaUnloadModel,
#     OllamaChatCompletion,
#     OllamaOptionTemperature,
#     OllamaOptionSeed,
#     OllamaOptionMaxTokens,
#     OllamaOptionTopP,
#     OllamaOptionTopK,
#     OllamaOptionRepeatPenalty,
#     OllamaOptionExtraBody,
#     OllamaDebugHistory,
#     OllamaHistoryLength,
#     _run_async,
#     _fetch_models,
# )
# ---------------------------------------------------------------------------
