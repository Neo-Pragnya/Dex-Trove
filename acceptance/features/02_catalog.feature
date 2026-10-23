@cap_catalog
Feature: People find the right dexterity
  Scenario: Search finds an item by what it does
    When I run "dex search motion --json"
    Then it succeeds
    And the JSON output at "id" contains "neo-pragnya/interactive-web-motion"

  Scenario: Filters narrow by kind and by source
    When I run "dex list --kind hook --json"
    Then it succeeds
    And the JSON output at "kind" equals ["hook", "hook", "hook", "hook", "hook", "hook", "hook"]
    When I run "dex list --source neo-pragnya --json"
    Then it succeeds
    And the JSON output has at least 5 items
    And the JSON output at "id" contains "neo-pragnya/living-diagrams"

  Scenario: show reports licence, provenance and the Ananke reference
    When I run "dex show neo-pragnya/living-diagrams --json"
    Then it succeeds
    And the JSON output at "kind" equals "skill"
    And the output contains "MIT"
    And the output contains "ananke"

  Scenario: Sources and candidates are listed
    When I run "dex sources --json"
    Then it succeeds
    And the JSON output at "sources.id" contains "awesome-copilot"
