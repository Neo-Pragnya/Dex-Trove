---
name: github-pr-evidence
description: "Open a pull request only after a person approves a local, static preview of the branch, commits, body and evidence hashes; then attach verified evidence (sha256 of reports, SBOMs, test results) as a PR comment or release assets. Use when someone asks to open, create or publish a PR, attach test or scan results to a PR, or prepare a PR from `dev review --pr-body`, even if they don't say MCP."
---

# Pull requests with evidence

This skill drives the **`dex-github`** MCP server that ships with Dex Trove (`dex mcp serve github`). The server runs
on your machine over stdio, uses only the Python standard library, and is dry-run by default: tools that change an
external system are refused unless the server was started with `--allow-actions`, and even then they need the
approval digest of the exact plan a person saw.

## Set it up

```bash
uv tool install dex-trove            # or: pipx install dex-trove
dex mcp config github --client claude-code    # prints: claude mcp add dex-github -- uvx --from dex-trove==… dex mcp serve github --root .
dex mcp config github --client vscode         # .vscode/mcp.json entry; also: codex, json
```

Add `--allow-actions` to the served command only in a session where actions are wanted.

Requires `git` and the GitHub CLI (`gh auth login`). A PR body file, for example from Dev Guru:

```bash
dev review --pr-body PR.md
```

## Tools

| Tool | What it does |
| --- | --- |
| `github_pr_preview` | Branch, commits, title, body and evidence hashes as a static local preview, with an approval digest. Pushes and creates nothing. |
| `github_pr_create` | Pushes the previewed commit and opens the pull request. Needs --allow-actions and the approval digest the user accepted; returns the existing PR instead of a duplicate. |
| `github_pr_attach_preview` | Re-hashes evidence for a PR and shows the comment that would be posted. Posts nothing. |
| `github_pr_attach` | Posts the evidence comment (and uploads to a release when asked). Needs --allow-actions and approval. |

## How to use it

1. `github_pr_preview body evidence`: branch, base, commits ahead, title, body and evidence sha256s, written to `dex-evidence/github/pr-preview.html` (no forms or scripts) and `.md`. Blocked when the tree is dirty, the branch is the base, or nothing is ahead.
2. Show the preview; ask for approval.
3. `github_pr_create ... approval` (with `--allow-actions`): pushes the previewed commit and runs `gh pr create` (draft by default). An open PR for the branch is returned instead of a duplicate; each step's outcome is reported.
4. `github_pr_attach_preview pr evidence expected`, then `github_pr_attach ... approval`: re-hashes the files, refuses any that changed, and posts the evidence table.

## Rules

- The static preview can't create anything; only the approved tool call can.
- Pass `expected` hashes from the preview so changed evidence is refused.
- Credentials come from the environment only. Results, logs and evidence are redacted.
- Every result has the same envelope: `status`, `artifacts` (with sha256), `findings`, `warnings`, `provenance` and a
  `digest` that ignores timestamps. Findings are also written as SARIF under `dex-evidence/github/`, where
  `ananke triage findings` reads them.
- Every action, approved or refused, is appended to `.dex/mcp/audit.jsonl`.

## What has been verified

Tested with a real git repository pushing to a local bare remote and a fake `gh` (preview, approval, duplicates, push and create failures, changed evidence). Not yet run against github.com.

From the shell, the same tools run once with `dex mcp call github <tool> --args '{...}'`.
