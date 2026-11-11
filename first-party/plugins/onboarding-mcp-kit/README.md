# Onboarding from document exports

Installs the `dex-onboarding` MCP server (from the `dex-trove` package), the [`onboarding-from-exports`](../../skills/onboarding-from-exports/SKILL.md) skill and the [`onboarding-guide`](../../agents/onboarding-guide.agent.md) agent.

The server is dry-run by default. To allow approved actions, change the server's args to end with `--allow-actions` in a session where you want them.

## What has been verified

Tested on a Confluence-style HTML export, a Word file, Markdown with an injection attempt, a restricted file and PDF pages through a fake pdftotext (citations, revocation, stable index). Not yet run on a real Confluence space export.
