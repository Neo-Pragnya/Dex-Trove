@cap_learn
Feature: Learning admits only what may be redistributed, and says why for the rest
  Background:
    Given a maintainer checkout learning the fixture upstreams

  Scenario: A dry run reports and writes nothing
    When I run "dex learn --dry-run"
    Then it succeeds
    And the output contains "excluded"
    And the file "trove" does not exist

  Scenario: Allowed items are admitted with their licence evidence
    When I run "dex learn"
    Then it succeeds
    And the file "trove/skills/good.csv-summary/SKILL.md" exists
    And the file "trove/skills/good.csv-summary/ananke.yaml" exists
    And the JSON file "trove/skills/good.csv-summary/dex.json" at "license.spdx" equals "MIT"
    And the JSON file "trove/skills/mixed.apache-skill/dex.json" at "license.spdx" equals "Apache-2.0"
    And the file "trove/skills/mixed.apache-skill/LICENSE.upstream" contains "Apache License"
    And the JSON file "trove/skills/good.release-notes/dex.json" at "tags" equals ["executes-code", "good", "skill"]
    When I run "dex validate"
    Then it succeeds

  Scenario: Every refused item is recorded with its reason
    When I run "dex learn"
    Then it succeeds
    And the file "trove/skills/mixed.proprietary-skill" does not exist
    And the file "trove/skills/mixed.leaky-skill" does not exist
    And the file "trove/EXCLUDED.json" contains "restrictive terms"
    And the file "trove/EXCLUDED.json" contains "no licence found"
    And the file "trove/EXCLUDED.json" contains "bundled GPL-3.0-only"
    And the file "trove/EXCLUDED.json" contains "aws-access-key in SKILL.md"
    And the JSON file "trove/EXCLUDED.json" at "excluded.reason" contains "size"

  Scenario: Credentials never reach the trove, in any file
    When I run "dex learn && grep -rIl 'AKIA[A-Z0-9]\{16\}' trove || echo none-found"
    Then the output contains "none-found"

 
  Scenario: An exact duplicate of a higher-priority item is refused on the first learn
    When I run "dex learn"
    Then it succeeds
    And the file "trove/skills/mixed.csv-summary" does not exist
    And the JSON file "trove/EXCLUDED.json" at "excluded.reason" contains "duplicate"

 
  Scenario: Learning twice from unchanged upstreams changes nothing
    Given I have run "dex learn"
    And the changes are committed
    When I run "dex learn && git status --porcelain"
    Then it succeeds
    And the output does not contain " M trove/"
    And the output does not contain " D trove/"

  Scenario: An upstream content change bumps the item's version
    Given I have run "dex learn"
    When I run:
      """
      printf '\nA new paragraph.\n' >> upstreams/good-up/skills/csv-summary/SKILL.md
      git -C upstreams/good-up -c commit.gpgsign=false commit -qam change
      dex learn
      """
    Then it succeeds
    And the JSON file "trove/skills/good.csv-summary/dex.json" at "version" equals "1.0.1"
