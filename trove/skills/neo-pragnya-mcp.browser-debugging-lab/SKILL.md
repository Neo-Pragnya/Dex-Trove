---
name: browser-debugging-lab
description: "Debug a web UI with Playwright without installing a browser into your tools: create an isolated, read-only Playwright lab against a local or named test URL, run it on approval, read trace.zip files (failed actions, console and page errors, failed requests), map failing selectors and pages to the frontend source and routes, and write redacted evidence. Use for flaky or failing UI tests, Playwright traces, front-end errors, selectors that stopped matching, or browser evidence for a bug, even if they don't say MCP."
---

# Browser debugging lab

This skill drives the **`dex-browser`** MCP server that ships with Dex Trove (`dex mcp serve browser`). The server runs
on your machine over stdio, uses only the Python standard library, and is dry-run by default: tools that change an
external system are refused unless the server was started with `--allow-actions`, and even then they need the
approval digest of the exact plan a person saw.

## Set it up

```bash
uv tool install dex-trove            # or: pipx install dex-trove
dex mcp config browser --client claude-code    # prints: claude mcp add dex-browser -- uvx --from dex-trove==… dex mcp serve browser --root .
dex mcp config browser --client vscode         # .vscode/mcp.json entry; also: codex, json
```

Add `--allow-actions` to the served command only in a session where actions are wanted.

.dex/browser.json lists any non-local test hosts the lab may use:

```json
{"test_hosts": ["staging.example.test"]}
```

Running the lab needs Node.js; it downloads `@playwright/test` (pinned) from npm, and Chromium unless `channel` is `chrome` or `msedge`.

## Tools

| Tool | What it does |
| --- | --- |
| `browser_lab_create` | Writes an isolated, read-only Playwright project pinned to an exact version, and the approval digest for running it. Installs and runs nothing. |
| `browser_lab_run` | Installs Playwright and Chromium into the lab and runs it. Downloads software: needs --allow-actions and the approval digest the user accepted. |
| `browser_trace` | Actions, failures, console and page errors, failed requests, screenshots and DOM snapshots in a trace. |
| `browser_map` | Maps failing selectors and pages (from a trace, or given) to frontend source and route definitions. |
| `browser_evidence` | Writes a redacted evidence bundle and SARIF for a trace; screenshots only when asked. |

## How to use it

1. `browser_lab_create name base_url pages sensitive_selectors channel`: writes `browser-lab/<name>/` (trace on, one worker, no retries, read-only checks, masked screenshots) and an approval digest. `channel: chrome` (or `msedge`) uses the installed browser, with no browser download.
2. `browser_lab_run ... approval` with `--allow-actions`, or bring an existing `trace.zip`.
3. `browser_trace trace`: actions and their outcome, console and page errors, failed requests, screenshots, DOM snapshots.
4. `browser_map trace paths`: failing selectors to `data-testid`, ids, classes, roles, labels and text in the source; failing URLs to route definitions.
5. `browser_evidence trace run_id`: a redacted bundle and SARIF under `dex-evidence/browser/`; screenshots only with `include_screenshots`.

## Rules

- Never point the lab at production, and don't add steps that submit, delete or pay.
- Treat screenshots as confidential: masks cover only the selectors you listed.
- Credentials come from the environment only. Results, logs and evidence are redacted.
- Every result has the same envelope: `status`, `artifacts` (with sha256), `findings`, `warnings`, `provenance` and a
  `digest` that ignores timestamps. Findings are also written as SARIF under `dex-evidence/browser/`, where
  `ananke triage findings` reads them.
- Every action, approved or refused, is appended to `.dex/mcp/audit.jsonl`.

## What has been verified

Run for real with Playwright 1.48.2 and the installed Chrome against a local fixture site: the healthy page passed and the broken page failed (console error, failed request). The trace reader, source mapping and redacted evidence were checked on those real traces (format version 7), with secrets in console text and URLs removed. Unit tests cover the lab files, refusals, unsafe archives, mapping and redaction. Not yet run against a real application's test environment.

From the shell, the same tools run once with `dex mcp call browser <tool> --args '{...}'`.
