Feature: US2 — Browse and Select Available Models

  Scenario: Dropdown lists all installed models
    Given Ollama has two or more models installed
    When the user adds an OllamaModelSelector node connected to a working OllamaClient
    Then the dropdown widget lists all installed model names

  Scenario: Empty Ollama renders warning rather than error
    Given no models are installed in Ollama
    When the OllamaModelSelector node renders
    Then the dropdown is empty
    And the node displays a warning rather than raising an error

  Scenario: Selected model name is the node output
    Given a model is selected in the OllamaModelSelector dropdown
    When the node runs
    Then the output STRING is the exact model name returned by Ollama /api/tags
