Feature: The skill lab says what an item can do and costs, and runs none of it
  Background:
    Given a fresh project

  @cap_skill_lab
  Scenario: A first-party skill's permissions, cost and routing accuracy
    Given the file "cases.json" with content:
      """
      [{"prompt": "migrate our SAS programs to python pandas", "expect": true},
       {"prompt": "write a React component for a login form", "expect": false}]
      """
    When I run "dex lab neo-pragnya-mcp/sas-to-python --cases cases.json --json"
    Then it succeeds
    And the JSON output at "effectiveness.recall" equals 1.0
    And the JSON output at "effectiveness.false_triggers" equals 0
    And the output contains "always_loaded"

  @cap_skill_lab
  Scenario: The survey covers the whole catalog and blocks nothing it ships
    When I run "dex lab --survey --json"
    Then it succeeds
    And the JSON output at "blocked" equals []

  @cap_skill_lab
  Scenario: No item named is a clean error
    When I run "dex lab"
    Then the exit code is 2
