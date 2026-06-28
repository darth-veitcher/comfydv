Feature: US1 — Configure Ollama Connection

  Scenario: Default host connects to local Ollama
    Given Ollama is running at "http://localhost:11434"
    When the user creates an OllamaClient node with the default host value
    Then the node outputs a valid OLLAMA_CLIENT handle equal to "http://localhost:11434"

  Scenario: Connected selector refreshes when host changes
    Given an OllamaClient node wired to an OllamaModelSelector node
    When the user changes the host widget on the client node
    Then the selector fetches its model list from the new host

  Scenario: Unreachable host surfaces a named error
    Given the user sets the OllamaClient host to "http://localhost:19999"
    When a downstream node attempts to use the connection
    Then ComfyUI surfaces an error message that names "http://localhost:19999"
    And the ComfyUI server process does not crash or hang
