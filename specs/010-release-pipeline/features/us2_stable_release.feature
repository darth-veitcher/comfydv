Feature: US2 — Publish a stable release from main

  Scenario: A feat commit publishes a new minor version
    Given a merge to main with a feat commit since the last release
    When the pipeline runs
    Then it publishes a new minor version

  Scenario: Only fix commits publish a new patch version
    Given a merge to main with only fix commits since the last release
    When the pipeline runs
    Then it publishes a new patch version

  Scenario: A breaking change at 0.x publishes a new minor version
    Given a merge to main with a BREAKING CHANGE footer while the version is 0.x
    When the pipeline runs
    Then it publishes a new minor version

  Scenario: Only docs and chore commits publish no version
    Given a merge to main with only docs and chore commits
    When the pipeline runs
    Then it publishes no new version

  Scenario: pip installs the new stable release
    Given a new stable release
    When a user runs pip install comfydv
    Then pip installs that release

  Scenario: ComfyUI Manager shows the new stable release as latest
    Given a new stable release
    When a user opens ComfyUI Manager
    Then the Manager shows that release as latest
