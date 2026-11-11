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

  @cap_catalog
  Scenario: The capability matrix shows what exists and what is missing
    When I run "dex capabilities code-review --json"
    Then it succeeds
    And the output contains "skill:superpowers/requesting-code-review"
    When I run "dex capabilities --status missing"
    Then it succeeds
    And the output contains "bpmn-designer"
    When I run "dex capabilities nope"
    Then it fails cleanly

  @cap_template_candidates
  Scenario: A template becomes a pinned candidate that the gates hold until it's evaluated
    Given the file "tpl/LICENSE" with content:
      """
      MIT License

      Copyright (c) 2026 Example

      Permission is hereby granted, free of charge, to any person obtaining a copy
      of this software and associated documentation files (the "Software"), to deal
      in the Software without restriction, including without limitation the rights
      to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
      copies of the Software, and to permit persons to whom the Software is
      furnished to do so, subject to the following conditions:

      The above copyright notice and this permission notice shall be included in all
      copies or substantial portions of the Software.

      THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
      """
    And the file "tpl/pyproject.toml" with content:
      """
      [project]
      name = "{{ cookiecutter.package }}"
      """
    And the file "tpl/tests/test_app.py" with content:
      """
      def test_it():
          assert True
      """
    When I run "dex candidate from-template tpl --name service-scaffold --description 'A small service scaffold with tests. Use it to start a new HTTP service.' --version 1.0.0 --out cand/service-scaffold --json"
    Then it succeeds
    And the JSON output at "version" equals "1.0.0"
    And the JSON output at "license" equals "MIT"
    And the file "cand/service-scaffold/template/pyproject.toml" exists
    When I run "dex candidate check cand/service-scaffold"
    Then it fails
    And the output contains "evaluation cases failed"

  @cap_template_candidates @adversarial
  Scenario: A template without a licence is refused before anything is written
    Given the file "tpl/README.md" with content:
      """
      A template with no licence.
      """
    When I run "dex candidate from-template tpl --name no-licence --description 'A template that has no licence file and so cannot be shared at all.' --out cand/no-licence"
    Then the exit code is 2
    And the output contains "no licence"
    And the file "cand/no-licence/SKILL.md" does not exist
