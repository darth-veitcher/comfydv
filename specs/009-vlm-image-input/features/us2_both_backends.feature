Feature: US2 — Same image input on either backend

  Scenario: Swap Ollama for llama.cpp and the image path still works
    Given a workflow that describes an image via the chat node wired to Ollama
    When the connection node is swapped to a llama.cpp one (pointed at a server with a multimodal model) with no other change
    Then the workflow still returns a description of the same image

  Scenario: Both backends produce an image-grounded response
    Given equivalent image + prompt inputs on both backends
    When each workflow executes
    Then both produce a coherent image-grounded text response — no backend requires a different node, input shape, or wiring for the image
