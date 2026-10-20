Feature: Notices, catalog and website content regenerate from the trove
  Background:
    Given a maintainer checkout learning the fixture upstreams
    And I have run "dex learn"

  @cap_notices
  Scenario: Notices credit every source with its copyright lines
    When I run "dex notices"
    Then it succeeds
    And the file "THIRD_PARTY_NOTICES.md" contains "Copyright (c) 2026 Good Upstream Authors"
    And the file "THIRD_PARTY_NOTICES.md" contains "Apache-2.0"

  @cap_notices
  Scenario: The catalog is rebuilt from the items on disk
    When I run "rm trove/catalog.json && dex catalog"
    Then it succeeds
    And the output matches "catalog: \d+ items"
    And the file "trove/catalog.json" exists

  @cap_docs_export
  Scenario: Docs export writes one page per item for the website
    When I run "dex docs export --out site-src"
    Then it succeeds
    And the output matches "exported \d+ item pages"
    And a file matching "site-src/content/items/*.md" exists
