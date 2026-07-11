Feature: US1 — Connect to a local inference server and get chat responses

  Scenario: Client node feeds a chat node
    Given a running local inference server and a workflow with a client node wired into a chat node
    When the workflow executes
    Then the chat node returns the model's text response

  Scenario: Unreachable server surfaces a clear error
    Given a client node configured with an unreachable server address
    When the workflow executes
    Then the chat node reports a clear connection error rather than hanging indefinitely or crashing the workflow

  Scenario: One client node configures multiple chat nodes
    Given two chat nodes in the same workflow wired to the same client node
    When the host address is changed on the client node
    Then both chat nodes use the new address without being edited individually
