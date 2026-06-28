Feature: US1 — Silent Normal Operation

  Scenario: No output during FormatString execution with valid template
    Given the comfydv package is imported with no logging configuration
    When FormatString.format_string is called with a valid simple template
    Then no lines are written to stdout or stderr by the comfydv package

  Scenario: No output when IS_CHANGED is called
    Given the comfydv package is imported with no logging configuration
    When FormatString.IS_CHANGED is called with a template string
    Then no lines are written to stdout or stderr by the comfydv package

  Scenario: No output when update_widget is called
    Given the comfydv package is imported with no logging configuration
    When FormatString.update_widget is called with a template string
    Then no lines are written to stdout or stderr by the comfydv package

  Scenario: No output during RandomChoice execution
    Given the comfydv package is imported with no logging configuration
    When RandomChoice.random_choice is called with valid inputs
    Then no lines are written to stdout or stderr by the comfydv package
