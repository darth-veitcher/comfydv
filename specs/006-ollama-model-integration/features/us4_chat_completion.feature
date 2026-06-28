Feature: US4 — Generate Text via Chat Completion

  Scenario: Chat Completion shows live dropdown (fixes Issue #1)
    Given a Chat Completion node connected to a working OllamaClient
    When the node is placed on the canvas
    Then the model field displays a live dropdown populated from Ollama
    And the model field is NOT a plain text input box

  Scenario: Single-turn completion returns non-empty response
    Given a prompt "Say exactly: pong" is wired into Chat Completion
    And the model "lukey03/qwen3.5-9b-abliterated-vision:latest" is selected
    When the node runs with an empty history
    Then the response output is a non-empty STRING
    And the updated_history output contains exactly 2 entries (user + assistant)

  Scenario: Multi-turn completion receives full conversation context
    Given a first Chat Completion turn with prompt "My name is Alice"
    When a second Chat Completion run uses the first turn's history and asks "What is my name?"
    Then the response contains "Alice"
    And the updated_history output contains exactly 4 entries

  Scenario: Generation options are forwarded to the Ollama API
    Given an OllamaOptionTemperature node set to 0.0 and OllamaOptionSeed set to 42
    And both are wired into Chat Completion
    When the workflow runs twice with the same prompt
    Then both response outputs are identical
