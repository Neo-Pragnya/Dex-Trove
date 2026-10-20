@cap_packaging
Feature: The package installs with the whole trove inside
  Scenario: The CLI reports the version being released
    When I run "dex --version"
    Then it succeeds
    And the output names the package version

  Scenario: The wheel carries every item, and every manifest is valid
    When I run "dex list --json"
    Then it succeeds
    And the JSON output has at least 900 items
    When I run "dex validate"
    Then it succeeds
    And the output contains "items valid"

  Scenario: Ananke can discover the trove through the entry point
    When I run:
      """
      python - <<'PY'
      from importlib.metadata import entry_points
      print([e.value for e in entry_points(group="ananke.troves")])
      PY
      """
    Then it succeeds
    And the output contains "dex_trove.paths:trove_root"

  Scenario: The CLI starts quickly
    When I run "dex --help"
    Then it succeeds
    And it finishes within 5 seconds
