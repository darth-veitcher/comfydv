Feature: US2 — One-click install via ComfyUI Manager UI

  Scenario: comfydv appears in Manager search
    Given a ComfyUI and Manager installation
    When the user searches comfydv in Manager
    Then a result appears with title Comfy DV Nodes and an accurate description

  Scenario: Manager install succeeds without errors
    Given the Manager search result for comfydv
    When the user clicks Install
    Then Manager clones the repo and runs pip install -r requirements.txt without errors

  Scenario: All three nodes appear after Manager install
    Given a Manager-installed comfydv
    When ComfyUI restarts
    Then all three nodes Format String Random Choice and Circuit Breaker appear in the dv/ node menu
