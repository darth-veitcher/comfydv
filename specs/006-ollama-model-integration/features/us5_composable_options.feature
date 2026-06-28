Feature: US5 — Tune Inference with Composable Option Nodes

  Scenario: Temperature 0.0 produces deterministic output
    Given an OllamaOptionTemperature node set to 0.0 wired to Chat Completion
    When the workflow runs twice with the same prompt and seed
    Then the response text is identical on both runs

  Scenario: Chained option nodes both reach the Ollama API
    Given OllamaOptionTemperature (0.0) chained into OllamaOptionSeed (42)
    And both are wired to Chat Completion
    When the workflow runs twice with the same prompt
    Then both response texts are identical (confirming both options were honoured)

  Scenario: Missing options input uses Ollama server defaults
    Given a Chat Completion node with no options socket connected
    When the node runs
    Then the node executes without error using Ollama server-side defaults
