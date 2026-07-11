Feature: US2 — Get structured, validated output from llama.cpp

  Scenario: Valid structured response exposes typed fields, same as Ollama
    Given a chat node connected to llama.cpp with structured output enabled and a valid schema
    When the workflow executes and the model responds correctly
    Then each schema field is available as its own typed output, and no required field is blank

  Scenario: Invalid response retries then fails clearly, same as Ollama
    Given a llama.cpp-hosted model that returns invalid or incomplete structured output
    When the workflow executes
    Then the node retries automatically and, if still unsuccessful, fails with a clear error
