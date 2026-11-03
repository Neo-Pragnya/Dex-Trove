Feature: Sources added under their own licences arrive with their notices and limits
  Background:
    Given a fresh project

  @cap_learn
  Scenario: Named frameworks are in the installed trove, and gaps stay visible
    When I run "dex show skill:bmad-method/bmad-prd"
    Then it succeeds
    And the output contains "MIT"
    When I run "dex show skill:impeccable/impeccable"
    Then it succeeds
    And the output contains "Apache-2.0"
    When I run "dex show prompt:spec-kit/plan"
    Then it succeeds
    When I run "dex capabilities"
    Then it succeeds
    And the output contains "Jenkins"
