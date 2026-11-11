---
name: assistant-usage-analytics
description: "Report how GitHub Copilot and Claude Code are used, from sources a person consents to: Copilot metrics exports or the org metrics API, Claude Code session logs (token totals and tool names, never prompt text) and `ananke context eval` results; estimate tokens graph retrieval would save; render a local HTML report labelling every number observed, estimated or unknown. Use for Copilot usage, adoption, acceptance rates, token spend, AI assistant ROI or harness analytics, even if they don't say MCP."
---

# Assistant usage analytics

This skill drives the **`dex-analytics`** MCP server that ships with Dex Trove (`dex mcp serve analytics`). The server runs
on your machine over stdio, uses only the Python standard library, and is dry-run by default: tools that change an
external system are refused unless the server was started with `--allow-actions`, and even then they need the
approval digest of the exact plan a person saw.

## Set it up

```bash
uv tool install dex-trove            # or: pipx install dex-trove
dex mcp config analytics --client claude-code    # prints: claude mcp add dex-analytics -- uvx --from dex-trove==… dex mcp serve analytics --root .
dex mcp config analytics --client vscode         # .vscode/mcp.json entry; also: codex, json
```

Add `--allow-actions` to the served command only in a session where actions are wanted.

Sources are given in `analytics_consent`. For the API: a token that can read the organisation's Copilot metrics (`GH_TOKEN`) or `gh auth login`. For the estimate: `ananke context eval questions.json > eval.json`.

## Tools

| Tool | What it does |
| --- | --- |
| `analytics_consent` | Records which usage sources may be read. Nothing is read before this. Prompts are never copied. |
| `analytics_opt_out` | Deletes the consent and every local analytics file. |
| `analytics_sources` | Which consented sources are reachable, what they observe, and what stays unknown. |
| `analytics_fetch` | Saves the organisation's Copilot metrics from the GitHub API (read-only, needs consent). |
| `analytics_normalize` | Usage rows by day, editor, language, session and tool, without prompt text. |
| `analytics_estimate` | Estimated token saving from graph retrieval, using the measured saving from ananke context eval. |
| `analytics_report` | A local HTML report with observed and estimated charts, unknowns and recommendations. |

## How to use it

1. Ask the user which sources may be read, then `analytics_consent sources exports org sessions_dir context_eval`.
2. `analytics_sources`: what's reachable, what each source observes, and what stays unknown.
3. Optional `analytics_fetch` (Copilot metrics API, read-only).
4. `analytics_normalize`: rows by day, editor, language, session and tool; no prompt or response text.
5. `analytics_estimate`: measured retrieval saving applied to observed file-read tokens, labelled as an estimate with its method.
6. `analytics_report`: `dex-evidence/analytics/usage-report.html` with solid (observed) and dashed (estimated) bars, unknowns and recommendations. `analytics_opt_out` deletes everything collected.

## Rules

- Never claim per-user or per-prompt Copilot token counts: GitHub doesn't publish them.
- Keep the labels: observed, estimated, unknown.
- Credentials come from the environment only. Results, logs and evidence are redacted.
- Every result has the same envelope: `status`, `artifacts` (with sha256), `findings`, `warnings`, `provenance` and a
  `digest` that ignores timestamps. Findings are also written as SARIF under `dex-evidence/analytics/`, where
  `ananke triage findings` reads them.
- Every action, approved or refused, is appended to `.dex/mcp/audit.jsonl`.

## What has been verified

Tested on a Copilot metrics export in the documented API format, a fake metrics API and Claude Code session logs (no prompt text stored, opt-out deletes everything). Not yet run against a real organisation's metrics API.

From the shell, the same tools run once with `dex mcp call analytics <tool> --args '{...}'`.
