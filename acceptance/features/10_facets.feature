@cap_facets
Feature: People find capabilities by what they're for, not just by name
  # Typed facets (task, methodology, phase, role…) with explainable filters. See docs/guides/finding-capabilities.md.

  Scenario: Filters combine as OR within a facet and AND across facets
    When I run:
      """
      dex search --methodology tdd --methodology bdd --phase testing --json -n 500 | python -c '
      import json, sys
      out = json.load(sys.stdin)
      assert out["total"] >= 5, out["total"]
      for r in out["results"]:
          assert set(r["facets"]["methodology"]) & {"tdd", "bdd"}, r["id"]
          assert "testing" in r["facets"]["phase"], r["id"]
      print("ok", out["total"])'
      """
    Then it succeeds
    And the output contains "ok"

  Scenario: The method skills a person reviewed rank first and say so
    When I run "dex search --methodology tdd --phase testing --explain --json"
    Then it succeeds
    And the JSON output at "results[0].id" equals "superpowers/test-driven-development"
    And the JSON output at "results[0].why.review_status" equals "approved"

  Scenario: Items without a facet never match it, and empty results say which filter to drop
    When I run "dex search --methodology adlc --role qa-engineer --phase verification --task generate-api-tests --language python --json"
    Then it succeeds
    And the JSON output at "total" equals 0
    And the JSON output at "relaxations.task" equals 1

  @cap_cli_ux
  Scenario: An unknown facet value is a clean error that lists the valid ones
    When I run "dex search --methodology waterfall"
    Then the exit code is 2
    And the output contains "choose from"
    And the output contains "adlc"

  Scenario: Aliases mean the same value, and SDLC and ADLC stay distinct
    When I run "dex search --role test-engineer --framework playwright --json"
    Then it succeeds
    And the JSON output at "query.all.role" equals ["qa-engineer"]
    When I run "dex facets list methodology --json"
    Then it succeeds
    And the JSON output at "facets.methodology.terms.sdlc.label" equals "SDLC"
    And the JSON output at "facets.methodology.terms.adlc.label" equals "ADLC"

  Scenario: Plain word search keeps its original output
    When I run "dex search motion --json"
    Then it succeeds
    And the JSON output at "id" contains "neo-pragnya/interactive-web-motion"

  Scenario: An item's facets show where each value came from
    When I run "dex facets show superpowers/test-driven-development --json"
    Then it succeeds
    And the JSON output at "classification.review_status" equals "approved"
    And the JSON output at "provenance.methodology.source" equals "curated"
    And the JSON output at "facets.platform" contains "claude-code"
    When I run "dex facets show awesome-copilot/playwright-python --json"
    Then it succeeds
    And the JSON output at "classification.review_status" equals "review-pending"
    And the JSON output at "facets.framework" contains "playwright"

  Scenario: The shipped facets sidecar is current
    # dex validate rebuilds facets from the shipped catalog, taxonomy and curation and compares (no network).
    When I run "dex validate"
    Then it succeeds
    When I run "dex facets list --json"
    Then it succeeds
    And the JSON output at "facets.task.terms.write-tests.items" equals 113
