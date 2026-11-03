@cap_releases
Feature: Learning appends releases and never rewrites them
  Background:
    Given a maintainer checkout learning the fixture upstreams

  Scenario: A changed upstream adds a release; released versions are immutable
    When I run "dex learn"
    Then it succeeds
    And the file "trove/releases.json" contains "skill:good/csv-summary"
    And the JSON file "trove/install-checks.json" at "items.skill:good/csv-summary.claude" equals "pass"
    When I run:
      """
      printf -- '---\nname: csv-summary\ndescription: Summarise a CSV file, now with medians.\n---\n\nMedians too.\n' > upstreams/good-up/skills/csv-summary/SKILL.md
      dex learn && dex release list good/csv-summary --json
      """
    Then it succeeds
    And the output contains "1.0.1"
    And the output contains "1.0.0"
    Given the changes are committed
    When I run "dex validate --since HEAD"
    Then it succeeds
    When I run:
      """
      python3 -c "import json,pathlib; p=pathlib.Path('trove/releases.json'); d=json.loads(p.read_text()); d['items']['skill:good/csv-summary']['releases'][0]['content_hash']='f'*64; p.write_text(json.dumps(d))"
      dex validate --since HEAD
      """
    Then it fails
    And the output contains "releases are immutable"

  Scenario: The reuse matrix is generated from the trove
    When I run "dex learn"
    Then it succeeds
    When I run "dex docs reuse"
    Then it succeeds
    And the file "docs/reference/reuse-matrix.md" contains "license-denied"
