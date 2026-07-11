Feature: US3 — Manage which models are resident in memory

  Scenario: List models with current status
    Given a running local server with at least one available model
    When a workflow author uses the model-listing node
    Then they see each available model along with its current status

  Scenario: Load a model into memory
    Given a model that is not currently loaded
    When a workflow author runs the load-model node against it
    Then the model becomes loaded and is then usable by the chat node

  Scenario: Unload a model from memory
    Given a model that is loaded and idle
    When a workflow author runs the unload-model node against it
    Then the model is freed from memory and its reported status updates accordingly
