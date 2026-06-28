Feature: US1 — Clean dependency install from a fresh clone

  Scenario: pip install from requirements.txt in a clean virtualenv
    Given a fresh clone with no pre-installed packages
    When pip install -r requirements.txt is executed
    Then it exits 0 and jinja2 is importable

  Scenario: Jinja2 template rendering succeeds after install
    Given the installed environment
    When FormatString is exercised with a Jinja2 template
    Then no ImportError or ModuleNotFoundError is raised

  Scenario: aiohttp web routes register without ImportError
    Given the installed environment
    When the aiohttp web routes in FormatString are registered
    Then no ImportError is raised
