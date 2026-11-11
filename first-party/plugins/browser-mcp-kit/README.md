# Browser debugging lab

Installs the `dex-browser` MCP server (from the `dex-trove` package), the [`browser-debugging-lab`](../../skills/browser-debugging-lab/SKILL.md) skill and the [`browser-debugger`](../../agents/browser-debugger.agent.md) agent.

The server is dry-run by default. To allow approved actions, change the server's args to end with `--allow-actions` in a session where you want them.

## What has been verified

Run for real with Playwright 1.48.2 and the installed Chrome against a local fixture site: the healthy page passed and the broken page failed (console error, failed request). The trace reader, source mapping and redacted evidence were checked on those real traces (format version 7), with secrets in console text and URLs removed. Unit tests cover the lab files, refusals, unsafe archives, mapping and redaction. Not yet run against a real application's test environment.
