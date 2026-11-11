Feature: Local MCP servers work offline, leave evidence, and never act without approval
  Background:
    Given a fresh project

  @cap_mcp_servers
  Scenario: Every server is listed with its tools and the tracker tasks it covers
    When I run "dex mcp list --json"
    Then it succeeds
    And the JSON output has at least 7 items
    And the output contains each of:
      """
      jenkins_trigger
      kibana_export
      github_pr_create
      sas_parity
      onboarding_guide
      browser_trace
      analytics_report
      """

  @cap_mcp_servers
  Scenario: A client can start a server and talk to it over stdio
    When I run "dex mcp serve sas --root ." with input:
      """
      {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "acceptance"}}}
      {"jsonrpc": "2.0", "method": "notifications/initialized"}
      {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
      {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "sas_inventory", "arguments": {"paths": ["missing.sas"]}}}
      """
    Then it succeeds
    And the output contains "serverInfo"
    And the output contains "dex-sas"
    And the output contains "sas_lineage"
    And the output contains "isError"
    And the output contains "not found"

  @cap_mcp_servers
  Scenario: Registration is printed, pinned to the installed version, and changes nothing
    When I run "dex mcp config kibana --client vscode"
    Then it succeeds
    And the output contains "dex-trove=="
    And the output contains "dex-kibana"
    And the file ".vscode/mcp.json" does not exist

  @cap_mcp_servers @adversarial
  Scenario: An action is refused when the server wasn't started with --allow-actions
    When I run:
      """
      dex mcp call browser browser_lab_create --args '{"name": "shop", "base_url": "http://127.0.0.1:8080"}'
      """
    Then it succeeds
    And the file "browser-lab/shop/playwright.config.ts" contains "trace: 'on'"
    And the output contains "sha256:"
    When I run:
      """
      dex mcp call browser browser_lab_run --args '{"name": "shop", "base_url": "http://127.0.0.1:8080", "approval": "sha256:0"}'
      """
    Then it fails cleanly
    And the output contains "actions are off"
    And the file ".dex/mcp/audit.jsonl" contains "refused"
    And the path "browser-lab/shop/node_modules" does not exist anywhere

  @cap_mcp_servers @adversarial
  Scenario: The lab refuses a production URL and paths outside the project
    When I run:
      """
      dex mcp call browser browser_lab_create --args '{"name": "prod", "base_url": "https://shop.example.com"}'
      """
    Then it fails cleanly
    And the output contains "never production"
    When I run:
      """
      dex mcp call sas sas_inventory --args '{"paths": ["../../etc"]}'
      """
    Then it fails cleanly
    And the output contains "outside the project root"

  @cap_mcp_servers
  Scenario: SAS steps get verdicts and a draft that refuses to run untranslated steps
    Given the file "etl/claims.sas" with content:
      """
      data work.big; set raw.claims; where amount > 100; net = amount - fee; run;
      proc sort data=work.big out=work.sorted; by region; run;
      data work.running; set work.sorted; retain cum 0; cum = cum + net; run;
      """
    When I run "dex mcp call sas sas_lineage"
    Then it succeeds
    And the JSON output at "counts.supported" equals 2
    And the JSON output at "counts.unsupported" equals 1
    And the file "dex-evidence/sas/sas-lineage.sarif" contains "RETAIN"
    When I run "dex mcp call sas sas_draft"
    Then it succeeds
    And the file "sas_draft.py" contains "sas_gt(df["
    And the file "sas_draft.py" contains "not_translated('etl/claims.sas:3"

  @cap_mcp_servers
  Scenario: Onboarding reads only permitted exports, cites sections and forgets on revocation
    Given the file "exports/team.md" with content:
      """
      # Team

      ## Access

      Request VPN access through the SSO portal on your first day.
      """
    And the file "exports/hr.md" with content:
      """
      # HR

      Salary bands for every engineer are listed here.
      """
    When I run:
      """
      dex mcp call onboarding onboarding_permit --args '{"paths": ["exports/team.md"], "classification": "internal"}'
      """
    Then it succeeds
    When I run:
      """
      dex mcp call onboarding onboarding_permit --args '{"paths": ["exports/hr.md"], "classification": "restricted"}'
      """
    Then it succeeds
    When I run "dex mcp call onboarding onboarding_import"
    Then it succeeds
    And the JSON output at "restricted_not_indexed" contains "exports/hr.md"
    When I run:
      """
      dex mcp call onboarding onboarding_search --args '{"query": "VPN access"}'
      """
    Then it succeeds
    And the output contains "exports/team.md § Access"
    And the file ".dex/mcp/onboarding/index.json" does not contain "Salary"
    When I run:
      """
      dex mcp call onboarding onboarding_revoke --args '{"paths": ["exports/team.md"]}'
      """
    Then it succeeds
    And the file ".dex/mcp/onboarding/index.json" does not contain "VPN"

  @cap_mcp_servers
  Scenario: A first-party MCP plugin installs its skill and agent
    When I run "dex install neo-pragnya-mcp/jenkins-mcp-kit --target claude --scope project"
    Then it succeeds
    And the file ".claude/skills/jenkins-build-gate/SKILL.md" exists
    And a file matching ".claude/agents/jenkins-build-steward*" exists
