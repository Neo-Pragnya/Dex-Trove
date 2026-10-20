@cap_licence
Feature: Licences are judged from their text
  Background:
    Given a fresh project
    And the fixture "upstreams" is copied to "upstreams"

  Scenario: MIT text is allowed
    When I run "dex license upstreams/good-up/LICENSE"
    Then it succeeds
    And the output contains "MIT → allow"

  Scenario: Restrictive terms are denied, whatever the file is called
    When I run "dex license upstreams/mixed-up/skills/proprietary-skill/LICENSE.txt"
    Then the output contains "→ deny"
    And the output contains "restrictive terms"

  Scenario: Copyleft text is denied
    When I run "dex license upstreams/mixed-up/skills/gpl-bundle/vendor/LICENSE"
    Then the output contains "GPL-3.0-only → deny"
