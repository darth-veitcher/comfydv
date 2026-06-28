Feature: US3 — Load and Unload Models

  Scenario: Load Model shows live dropdown (fixes Issue #1)
    Given a Load Model node connected to a working OllamaClient
    When the node is placed on the canvas
    Then the model field displays a live dropdown populated from Ollama
    And the model field is NOT a plain text input box

  Scenario: Load Model loads model into Ollama memory
    Given a model is selected in the Load Model dropdown
    When the node runs
    Then Ollama reports the model as loaded
    And the node output STRING equals the selected model name

  Scenario: Unload Model evicts model from Ollama memory
    Given an OllamaUnloadModel node wired to a client and a model name
    When the node runs
    Then Ollama evicts the model from memory
    And the node output STRING equals the model name

  Scenario: Empty model name is rejected before contacting Ollama
    Given an OllamaLoadModel or OllamaUnloadModel node
    When the node runs with an empty model name
    Then the node raises a validation error
    And no HTTP request is sent to Ollama
