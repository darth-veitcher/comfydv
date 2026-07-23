Feature: US3 — Structured output about an image

  Scenario: Structured fields populated from the image
    Given the chat node with an image wired and structured output enabled with a valid schema
    When the workflow executes against a vision-capable model
    Then each schema field is available as its own typed output, populated from the image, with no required field blank

  Scenario: Invalid structured output retries then fails clearly
    Given the same setup where the model first returns invalid or incomplete structured output
    When the workflow executes
    Then the node retries and, if still unsuccessful, fails with a clear error — the same retry/validation behaviour the text-only structured path already guarantees
