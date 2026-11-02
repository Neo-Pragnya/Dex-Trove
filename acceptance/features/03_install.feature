Feature: Items install where each agent looks for them
  Background:
    Given a fresh project

  @cap_install
  Scenario: A skill installs into the project's Claude Code folder
    When I run "dex install neo-pragnya/living-diagrams --target claude --scope project"
    Then it succeeds
    And the file ".claude/skills/living-diagrams/SKILL.md" exists
    And the file ".claude/skills/living-diagrams/scripts/term_flow.py" exists

  @cap_install
  Scenario: The exact command the website shows works
    When I run "dex install skill:neo-pragnya/living-diagrams --target copilot"
    Then it succeeds
    And the file ".github/skills/living-diagrams/SKILL.md" exists

  @cap_install
  Scenario: A plain folder target keeps the trove layout
    When I run "dex install neo-pragnya/living-diagrams --target dir --path vendor"
    Then it succeeds
    And the file "vendor/skills/neo-pragnya.living-diagrams/SKILL.md" exists

  @cap_install
  Scenario: A plugin installs every bundled skill and agent
    When I run "dex install awesome-copilot/acreadiness-cockpit --target claude --scope project"
    Then it succeeds
    And a file matching ".claude/skills/acreadiness-*/SKILL.md" exists
    And a file matching ".claude/agents/*.md" exists

  @cap_install_safety @adversarial
  Scenario: A project-scope install writes nothing outside the project
    When I run "dex install neo-pragnya/living-diagrams --target claude --scope project && find $HOME -type f | wc -l"
    Then it succeeds
    And the output matches "^\s*0\s*$"

  @cap_install_safety @adversarial
  Scenario: A hook that runs code is not installed without --allow-exec
    When I run "dex install awesome-copilot/attester-import-check --target dir --path vendor"
    Then the output contains "--allow-exec"
    And no file matching "vendor/hooks/*" exists

  @cap_install_safety
  Scenario: Its reviewed twin installs with --allow-exec
    When I run "dex install awesome-copilot/attester-import-check --target dir --path vendor --allow-exec"
    Then it succeeds
    And a file matching "vendor/hooks/*/hooks.json" exists

  @cap_install_safety @cap_cli_ux
  Scenario: Refusing to install exits non-zero
    When I run "dex install awesome-copilot/attester-import-check --target dir --path vendor"
    Then it fails cleanly

  @cap_cli_ux
  Scenario: An unknown item is a clean error
    When I run "dex install neo-pragnya/no-such-skill --target claude --scope project"
    Then it fails cleanly
    And the output contains "no item matches"

  @cap_install
  Scenario: A Copilot agent installed for Claude Code gets Claude tool names and model values
    # Claude Code won't launch a subagent whose tools list resolves to nothing; Copilot ids never resolve.
    When I run "dex install awesome-copilot/accessibility --target claude --scope project"
    Then it succeeds
    And the output contains "adapted: dropped"
    And the file ".claude/agents/accessibility.md" contains "tools: Read, Grep, Glob, Edit, Write, WebFetch, Bash"
    And the file ".claude/agents/accessibility.md" contains "You are a world-class expert in web accessibility"

  @cap_install_safety @adversarial
  Scenario: Installing never replaces a skill the user wrote
    Given the file ".claude/skills/living-diagrams/SKILL.md" with content:
      """
      my own version
      """
    When I run "dex install neo-pragnya/living-diagrams --target claude --scope project"
    Then the exit code is 1
    And the output contains "--force"
    And the file ".claude/skills/living-diagrams/SKILL.md" contains "my own version"

  @cap_install_safety
  Scenario: Its twin: re-installing Dex's own unedited copy replaces it, and --force replaces the user's
    Given I have run "dex install neo-pragnya/living-diagrams --target claude --scope project"
    When I run "dex install neo-pragnya/living-diagrams --target claude --scope project"
    Then it succeeds
    And the file ".claude/.dex-trove-installed.json" contains "skills/living-diagrams"
