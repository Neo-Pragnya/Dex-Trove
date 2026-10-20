@cap_privacy
Feature: Private items leave no trace
  Background:
    Given a maintainer checkout learning the fixture upstreams

  Scenario: A source's own .dexignore hides an item everywhere
    When I run "dex learn"
    Then it succeeds
    And the output contains "1 ignored"
    When I run "dex notices && grep -rIl -e private-notes -e PRIVATE-MARKER trove sources.yaml THIRD_PARTY_NOTICES.md || echo no-trace"
    Then the output contains "no-trace"

  Scenario: A user-level ignore file hides items without touching the repo
    Given the file "my-ignore" with content:
      """
      mixed:apache-skill
      """
    And the environment variable "DEX_TROVE_IGNORE" is "$PROJECT/my-ignore"
    When I run "dex learn"
    Then it succeeds
    And the file "trove/skills/mixed.apache-skill" does not exist
    And the file "trove/EXCLUDED.json" does not contain "apache-skill"
