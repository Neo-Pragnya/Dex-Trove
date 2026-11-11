# Jenkins build gate

Installs the `dex-jenkins` MCP server (from the `dex-trove` package), the [`jenkins-build-gate`](../../skills/jenkins-build-gate/SKILL.md) skill and the [`jenkins-build-steward`](../../agents/jenkins-build-steward.agent.md) agent.

The server is dry-run by default. To allow approved actions, change the server's args to end with `--allow-actions` in a session where you want them.

## What has been verified

Tested against a local fake Jenkins and fake GitHub API (allowlist, parameter rules, CSRF crumb, basic auth, 401 handling, idempotency, bounded polling, SARIF). Not yet run against a real Jenkins server.
