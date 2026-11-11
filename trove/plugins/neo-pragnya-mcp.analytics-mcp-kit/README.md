# Assistant usage analytics

Installs the `dex-analytics` MCP server (from the `dex-trove` package), the [`assistant-usage-analytics`](../../skills/assistant-usage-analytics/SKILL.md) skill and the [`usage-analyst`](../../agents/usage-analyst.agent.md) agent.

The server is dry-run by default. To allow approved actions, change the server's args to end with `--allow-actions` in a session where you want them.

## What has been verified

Tested on a Copilot metrics export in the documented API format, a fake metrics API and Claude Code session logs (no prompt text stored, opt-out deletes everything). Not yet run against a real organisation's metrics API.
