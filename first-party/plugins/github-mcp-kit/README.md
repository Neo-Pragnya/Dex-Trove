# Pull requests with evidence

Installs the `dex-github` MCP server (from the `dex-trove` package), the [`github-pr-evidence`](../../skills/github-pr-evidence/SKILL.md) skill and the [`pr-evidence-publisher`](../../agents/pr-evidence-publisher.agent.md) agent.

The server is dry-run by default. To allow approved actions, change the server's args to end with `--allow-actions` in a session where you want them.

## What has been verified

Tested with a real git repository pushing to a local bare remote and a fake `gh` (preview, approval, duplicates, push and create failures, changed evidence). Not yet run against github.com.
