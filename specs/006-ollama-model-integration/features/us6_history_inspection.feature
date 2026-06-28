Feature: US6 — Inspect Conversation History

  Scenario: Debug History shows both turns as a string
    Given a Chat Completion history containing 2 turns (user + assistant)
    When the history is wired to an OllamaDebugHistory node and the node runs
    Then the output STRING is a human-readable representation showing both turns

  Scenario: History Length counts turns correctly
    Given a Chat Completion history containing 3 turns
    When the history is wired to an OllamaHistoryLength node and the node runs
    Then the output INT is 3

  Scenario: Empty history is handled gracefully
    Given an empty history list (no prior turns)
    When wired to OllamaDebugHistory
    Then the output STRING is empty or "[]"
    When wired to OllamaHistoryLength
    Then the output INT is 0
