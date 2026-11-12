Feature: US1 — Block a merge that fails the quality gates

  Scenario: A failing unit test blocks a pull request to develop
    Given a pull request to develop with a failing unit test
    When the check runs
    Then the check reports a failure

  Scenario: A lint error blocks a pull request to main
    Given a pull request to main with a lint error
    When the check runs
    Then the check reports a failure

  Scenario: A clean pull request passes
    Given a pull request that passes all the gates
    When the check runs
    Then the check reports success

  Scenario: A fork pull request gets no publishing credentials
    Given a pull request from a fork
    When the check runs
    Then the check runs without access to the publishing credentials
