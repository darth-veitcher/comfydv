Feature: US4 — Map ComfyUI Manager nightly to develop

  Scenario: Record the branch that nightly clones
    Given comfydv is on the Comfy Registry
    When the maintainer installs nightly
    Then the record names the branch and commit that the Manager cloned

  Scenario: Record the decision in an ADR
    Given the record shows the default branch
    When the maintainer decides
    Then the decision and its evidence are in an ADR

  Scenario: The legacy git-clone entry stops cloning develop
    Given develop becomes the default branch
    When a user installs from the legacy git-clone entry
    Then that entry no longer clones develop
