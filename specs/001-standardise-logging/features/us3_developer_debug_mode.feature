Feature: US3 — Developer Debug Mode

  Scenario: DEBUG records appear when comfydv logger is configured at DEBUG
    Given the comfydv logger is configured with a handler at DEBUG level
    When FormatString.format_string is called with a valid template
    Then at least one DEBUG log record is emitted by the comfydv logger

  Scenario: No records appear when no logging is configured (NullHandler default)
    Given the comfydv package is imported with no logging configuration
    When FormatString.format_string is called with a valid template
    Then the comfydv logger has exactly one handler and it is a NullHandler
    And zero log records reach any external handler
