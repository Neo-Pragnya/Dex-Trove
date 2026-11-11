---
name: jenkins-build-gate
description: "Start allowlisted Jenkins jobs after a pull request only when its checks pass and a person approves the exact parameters; follow the build to its result and record evidence. Use when someone asks to trigger, rerun or start a Jenkins build or pipeline for a PR, check whether a job may run, or wait for a Jenkins result, even if they don't say MCP."
---

# Jenkins build gate

This skill drives the **`dex-jenkins`** MCP server that ships with Dex Trove (`dex mcp serve jenkins`). The server runs
on your machine over stdio, uses only the Python standard library, and is dry-run by default: tools that change an
external system are refused unless the server was started with `--allow-actions`, and even then they need the
approval digest of the exact plan a person saw.

## Set it up

```bash
uv tool install dex-trove            # or: pipx install dex-trove
dex mcp config jenkins --client claude-code    # prints: claude mcp add dex-jenkins -- uvx --from dex-trove==… dex mcp serve jenkins --root .
dex mcp config jenkins --client vscode         # .vscode/mcp.json entry; also: codex, json
```

Add `--allow-actions` to the served command only in a session where actions are wanted.

.dex/jenkins.json (in the project; no secrets):

```json
{"url": "https://jenkins.example.com",
 "jobs": {"app/ci": {"parameters": {"BRANCH": {"pattern": "^[A-Za-z0-9._/-]{1,100}$", "required": true},
                                    "SUITE": {"choices": ["smoke", "full"], "default": "smoke"}},
                     "require_pr": {"repo": "acme/app", "checks": "passing"}}},
 "poll": {"max_attempts": 60, "interval_seconds": 10}}
```

Environment: `JENKINS_USER` and `JENKINS_TOKEN` (an API token), and `GH_TOKEN` or a `gh auth login` for PR checks.

## Tools

| Tool | What it does |
| --- | --- |
| `jenkins_jobs` | The allowlisted jobs, their parameter rules, and builds started from this project. |
| `jenkins_check` | Is the job allowlisted, present and enabled in Jenkins, and are the PR's checks passing? |
| `jenkins_preview` | Validates parameters and shows exactly what would start, with an approval digest. Starts nothing. |
| `jenkins_trigger` | Starts the previewed build. Needs --allow-actions and the preview's approval digest, which the user must have seen and accepted. The same plan never starts twice. |
| `jenkins_status` | Follows a started build (bounded checks) and records its URL and outcome as evidence. |

## How to use it

1. `jenkins_jobs`: what may run here, and whether credentials are present.
2. `jenkins_check job pr`: the job exists and is enabled, the allowlisted parameters exist on Jenkins, and the PR is open with passing checks.
3. `jenkins_preview job parameters pr`: validates every parameter and returns the plan, an idempotency key and an `approval` digest. Show the summary to the user and ask.
4. `jenkins_trigger ... approval`: only after an explicit yes, and only when the server runs with `--allow-actions`. The same plan never starts twice; a repeat returns the first build.
5. `jenkins_status idempotency_key`: bounded polling; writes `dex-evidence/jenkins/build-<key>.json` and SARIF for a failed build.

## Rules

- Never call `jenkins_trigger` without the user's explicit approval of the preview they saw.
- If the PR moves (new commits), the digest changes: preview again.
- A refused request (401/403) means credentials; don't retry with other jobs.
- Credentials come from the environment only. Results, logs and evidence are redacted.
- Every result has the same envelope: `status`, `artifacts` (with sha256), `findings`, `warnings`, `provenance` and a
  `digest` that ignores timestamps. Findings are also written as SARIF under `dex-evidence/jenkins/`, where
  `ananke triage findings` reads them.
- Every action, approved or refused, is appended to `.dex/mcp/audit.jsonl`.

## What has been verified

Tested against a local fake Jenkins and fake GitHub API (allowlist, parameter rules, CSRF crumb, basic auth, 401 handling, idempotency, bounded polling, SARIF). Not yet run against a real Jenkins server.

From the shell, the same tools run once with `dex mcp call jenkins <tool> --args '{...}'`.
