Feature: US3 — See and control which models are loaded on llama.cpp

  Scenario: List models with full status vocabulary
    Given a running local llama-server with at least one available model
    When a workflow author uses the model-listing node
    Then they see each available model along with its current status, drawn from llama.cpp's full status vocabulary

  Scenario: Load a model into memory
    Given a model that is not currently loaded
    When a workflow author runs the load-model node against it
    Then the model becomes loaded and is then usable by the chat node

  Scenario: Unload a model from memory
    Given a model that is loaded and idle
    When a workflow author runs the unload-model node against it
    Then the model is freed from memory and its reported status updates accordingly
