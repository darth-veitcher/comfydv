Feature: US4 — Reconnect an existing workflow after upgrading

  Scenario: Renamed nodes are reported with a documented replacement
    Given a saved workflow using the current Ollama-specific node and connection-socket names
    When it is opened after upgrading
    Then ComfyUI reports the now-missing node types
    And documentation identifies the replacement node for each one

  Scenario: Reconnected workflow produces equivalent output
    Given a workflow that has been reconnected to the new generic nodes
    When it executes with the same inputs and model as before the upgrade
    Then it produces equivalent output
