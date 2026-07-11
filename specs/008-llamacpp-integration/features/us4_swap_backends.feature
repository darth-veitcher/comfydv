Feature: US4 — Swap from Ollama to llama.cpp without touching the rest of the workflow

  Scenario: Replacing only the connection node preserves the workflow
    Given a workflow with chat/model-management nodes wired to an Ollama connection node
    When a workflow author replaces only the connection node with a llama.cpp one, pointed at a running llama-server
    Then the workflow runs successfully with no changes to any other node
