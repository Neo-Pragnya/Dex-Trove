@cap_site @needs_chrome @needs_site
Feature: The website works for a visitor
  Scenario: Browser journeys pass on the built site
    When I run "node $REPO/acceptance/site/journeys.mjs $SITE_DIST"
    Then it succeeds
    And the output contains "journeys passed"
