Feature: US1 — Connect to a local llama.cpp server and get chat responses

  Scenario: llama.cpp connection node feeds the existing chat node
    Given a running local llama-server (router mode) and a workflow with a llama.cpp connection node wired into the existing chat node
    When the workflow executes
    Then the chat node returns the model's text response

  Scenario: Unreachable llama.cpp server surfaces a clear error
    Given the llama.cpp connection node configured with an unreachable server address
    When the workflow executes
    Then the chat node reports a clear connection error
