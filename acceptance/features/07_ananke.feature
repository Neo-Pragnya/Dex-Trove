@cap_ananke @slow
Feature: Ananke Plexus learns the trove
  Background:
    Given a fresh project
    And I have run "ananke init"
    And I have run "ananke registry init"

  Scenario: dex ananke sync registers a curated slice without denials
    When I run "dex ananke sync --project . --kind skill"
    Then it succeeds
    When I run "ananke skill list"
    Then it succeeds
    And the output contains "neo-pragnya/living-diagrams"

  Scenario: Ananke learns the whole wheel; placeholder secrets are refused by design
    When I run "ananke registry learn python:dex-trove"
    Then it does not crash
    And the output contains "SECRET_DETECTED"
    When I run "ananke registry list --json"
    Then the JSON output has at least 900 items
