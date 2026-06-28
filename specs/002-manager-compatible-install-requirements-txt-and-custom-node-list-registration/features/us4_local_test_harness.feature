Feature: US4 — Local test harness for install verification

  Scenario: Docker Compose starts CPU-only ComfyUI without a GPU
    Given a machine with Docker and no GPU
    When docker compose up --build is run from the repo root
    Then the ComfyUI server starts and curl http://localhost:8188/ returns 200

  Scenario: All three comfydv nodes load in the container
    Given the running container
    When the ComfyUI startup logs are inspected
    Then all three comfydv nodes FormatString RandomChoice and CircuitBreaker appear as loaded with no import errors

  Scenario: docker compose down exits cleanly
    Given the running container
    When docker compose down is run
    Then it exits cleanly with no lingering processes
