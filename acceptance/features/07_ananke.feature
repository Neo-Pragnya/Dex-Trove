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

  Scenario: A project switches Dex Trove on with Ananke's [troves] setting
    When I run "ananke registry troves list --json"
    Then it succeeds
    And the JSON output at "name" contains "dex-trove"
    When I run "ananke registry troves enable dex-trove --kind skill --namespace neo-pragnya"
    Then it succeeds
    When I run "ananke registry troves sync --json"
    Then it succeeds
    And the JSON output at "[0].denied" equals 0
    When I run "ananke skill list"
    Then the output contains "neo-pragnya/living-diagrams"
    And the output contains "neo-pragnya/capability-acceptance"
