Feature: US3 — Test a development build before users get it

  Scenario: A feat commit on develop publishes a pre-release
    Given a merge to develop with a feat commit
    When the pipeline runs
    Then it publishes a pre-release version to PyPI

  Scenario: A normal install ignores the pre-release
    Given a pre-release on PyPI
    When a user runs pip install comfydv
    Then pip installs the last stable release

  Scenario: An opt-in install gets the pre-release
    Given a pre-release on PyPI
    When the maintainer runs pip install --pre comfydv
    Then pip installs the pre-release

  Scenario: develop publishes nothing to the Comfy Registry
    Given a merge to develop
    When the pipeline runs
    Then it publishes nothing to the Comfy Registry
