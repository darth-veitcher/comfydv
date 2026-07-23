Feature: US1 — Describe an image with a chat node

  Scenario: Describe a wired image
    Given a chat node connected to a backend with a vision-capable model loaded and an image wired into the node's image input
    When the workflow executes with a prompt like "describe this image"
    Then the node returns a text response that reflects the actual content of the wired image

  Scenario: No image wired behaves exactly as today
    Given the same chat node with no image wired
    When the workflow executes
    Then the node behaves exactly as it does today — text-only chat, identical response for identical text input — with no new required inputs and no change in output
