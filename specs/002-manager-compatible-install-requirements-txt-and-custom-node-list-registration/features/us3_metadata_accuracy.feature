Feature: US3 — Package metadata accurately describes the current node set

  Scenario: @description references only existing nodes
    Given the root __init__.py
    When its @description is read
    Then it references only the three nodes that exist and makes no mention of non-existent functionality

  Scenario: Manager registry description is accurate
    Given the submitted Manager registry entry
    When a user reads the description
    Then it accurately reflects the package's current capabilities
