Feature: US2 — Get structured, validated output instead of parsing raw text

  Scenario: Valid structured response exposes typed fields
    Given a chat node with structured output enabled and a valid schema
    When the workflow executes and the model responds correctly
    Then each schema field is available as its own typed output, and no required field is blank

  Scenario: Invalid response triggers automatic retry
    Given a model that returns invalid, incomplete, or empty-required-field output
    When the workflow executes
    Then the node automatically retries the request up to a configured limit

  Scenario: Exhausted retries fail clearly instead of passing through bad data
    Given a model that continues to return invalid output after all retries are exhausted
    When the workflow executes
    Then the node fails with a clear, specific error rather than silently passing through invalid or partial data
