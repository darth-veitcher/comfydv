Feature: US2 — Errors Still Surface

  Scenario: Jinja2 template syntax error produces an ERROR log record
    Given the comfydv package is imported with a DEBUG-level log handler attached
    When FormatString.format_string is called with an invalid Jinja2 template
    Then at least one log record at ERROR level is emitted by the comfydv logger

  Scenario: Missing variable in Simple template produces an ERROR log record
    Given the comfydv package is imported with a DEBUG-level log handler attached
    When FormatString.format_string is called with a Simple template referencing an undefined variable
    Then at least one log record at ERROR level is emitted by the comfydv logger

  Scenario: File save failure produces an ERROR log record
    Given the comfydv package is imported with a DEBUG-level log handler attached
    When FormatString.format_string is called with an unwritable save_path
    Then at least one log record at ERROR level is emitted by the comfydv logger

  Scenario: CircuitBreaker with status False halts the queue run and emits a log record
    Given the comfydv package is imported with a DEBUG-level log handler attached
    When CircuitBreaker.doit is called with status set to False
    Then the queue run halts and a message is visible in the log output
