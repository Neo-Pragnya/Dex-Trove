Feature: Every version is remembered, pinned installs are exact, and new memory needs review
  Background:
    Given a fresh project

  @cap_releases
  Scenario: A lock pins an exact version and digest, and installs exactly that
    When I run "dex lock neo-pragnya/living-diagrams superpowers/systematic-debugging"
    Then it succeeds
    And the JSON file "dex.lock.json" at "schema" equals "dex-trove/lock@1"
    And the file "dex.lock.json" contains "content_hash"
    When I run "dex verify-lock"
    Then it succeeds
    And the output contains "2 pin(s) valid"
    When I run "dex install --locked --target claude --scope project"
    Then it succeeds
    And the file ".claude/skills/living-diagrams/SKILL.md" exists
    And the file ".claude/skills/systematic-debugging/SKILL.md" exists

  @cap_releases
  Scenario: Release history and fork lineage are visible
    When I run "dex release list superpowers/systematic-debugging --json"
    Then it succeeds
    And the JSON output at "key" equals "skill:superpowers/systematic-debugging"
    And the JSON output at "releases" has at least 1 items
    When I run "dex release lineage superpowers/systematic-debugging"
    Then it succeeds
    And the output contains "no forks recorded"

  @cap_releases @adversarial
  Scenario: A lock whose digest was tampered with is refused, and nothing is installed
    Given the file "dex.lock.json" with content:
      """
      {"schema": "dex-trove/lock@1", "items": [{"key": "skill:neo-pragnya/living-diagrams", "version": "1.0.0",
        "content_hash": "0000000000000000000000000000000000000000000000000000000000000000", "entry": "SKILL.md",
        "files": ["SKILL.md"], "source": {"repo": null, "commit": null, "path": "living-diagrams"}}]}
      """
    When I run "dex verify-lock"
    Then it fails
    And the output contains "digest differs"
    When I run "dex install --locked --target claude --scope project"
    Then it fails
    And the file ".claude/skills/living-diagrams" does not exist

  @cap_releases @adversarial
  Scenario: Changing the release ledger needs a maintainer checkout
    When I run "dex release yank neo-pragnya/living-diagrams@1.0.0 --reason test"
    Then it fails cleanly
    And the output contains "Dex-Trove checkout"

  @cap_relations
  Scenario: Related items are typed, reviewed and backed by evidence
    When I run "dex related superpowers/executing-plans --json"
    Then it succeeds
    And the output contains each of:
      """
      "type": "requires"
      "origin": "curated"
      skill:superpowers/writing-plans
      REQUIRED SUB-SKILL
      """
    And the output does not contain "compatible"

  @cap_candidates @adversarial
  Scenario: A candidate whose evaluation failed cannot be published
    Given the file "cand/fix-flaky-tests/SKILL.md" with content:
      """
      ---
      name: fix-flaky-tests
      description: Stabilise flaky tests by isolating time, randomness and order. Use when a test fails intermittently.
      license: MIT
      ---

      # Fix flaky tests
      """
    And the file "cand/fix-flaky-tests/evaluation.json" with content:
      """
      {"schema": "dex-trove/evaluation@1", "finished_at": "2026-11-02T00:00:00+00:00",
       "cases": [{"id": "pos-1", "kind": "positive", "passed": true}, {"id": "reg-1", "kind": "regression", "passed": false}]}
      """
    When I run "dex candidate check cand/fix-flaky-tests"
    Then it fails
    And the output contains "evaluation cases failed: reg-1"
    When I run "dex candidate review cand/fix-flaky-tests --approve --reviewer lead --reason ok"
    Then it succeeds
    When I run "dex candidate publish cand/fix-flaky-tests --to neo-pragnya"
    Then it fails
    And the output contains "inside a Dex-Trove checkout"

  @cap_candidates
  Scenario: A passing candidate passes every gate it can check
    Given the file "cand/fix-flaky-tests/SKILL.md" with content:
      """
      ---
      name: fix-flaky-tests
      description: Stabilise flaky tests by isolating time, randomness and order. Use when a test fails intermittently.
      license: MIT
      ---

      # Fix flaky tests
      """
    And the file "cand/fix-flaky-tests/evaluation.json" with content:
      """
      {"schema": "dex-trove/evaluation@1", "finished_at": "2026-11-02T00:00:00+00:00",
       "cases": [{"id": "pos-1", "kind": "positive", "passed": true}, {"id": "reg-1", "kind": "regression", "passed": true}]}
      """
    When I run "dex candidate check cand/fix-flaky-tests --json"
    Then it succeeds
    And the JSON output at "ok" equals true
    And the JSON output at "name" equals "fix-flaky-tests"

  @cap_releases
  Scenario: A lock hands Ananke exact pins without running anything
    When I run "dex lock superpowers/systematic-debugging agent:awesome-copilot/planner"
    Then it succeeds
    When I run "dex ananke handoff"
    Then it succeeds
    And the output contains each of:
      """
      [tool.ananke.skills]
      "superpowers/systematic-debugging" = "1.0.0"
      [[tool.ananke.agent]]
      name = "awesome-copilot/planner"
      """
    And the file "pyproject.toml" does not exist

  @cap_facets
  Scenario: The needs facet says what must be installed to run an item
    When I run "dex search --needs python --json -n 200"
    Then it succeeds
    And the JSON output at "results" has at least 5 items
    And the output contains "neo-pragnya/living-diagrams"

  @cap_relations
  Scenario: Overlapping items are grouped and scored on verifiable evidence
    When I run "dex overlap --json"
    Then it succeeds
    And the output contains each of:
      """
      skill:anthropic/webapp-testing
      install checks pass
      """
