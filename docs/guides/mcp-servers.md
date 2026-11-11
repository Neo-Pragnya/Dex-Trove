---
title: Local MCP servers
description: Seven MCP servers that ship with Dex for systems it can't reach by itself, dry-run by default, with skills, agents and plugins.
---

# Local MCP servers

Dex ships seven [Model Context Protocol](https://modelcontextprotocol.io/) servers for systems an assistant
shouldn't touch without care: Jenkins, Kibana, GitHub pull requests, SAS programs, exported company documents, a
browser and usage data. They run on your machine over stdio, use only the Python standard library (installing Dex
adds no dependency for them), and are imported only when served.

| Server | For | Acts on an external system |
| --- | --- | --- |
| `jenkins` | Start allowlisted Jenkins jobs after a PR whose checks pass; follow the build; record evidence | `jenkins_trigger` |
| `kibana` | Fields the code really logs, a checked dashboard spec, saved-object NDJSON, import into a test instance | `kibana_import` |
| `github` | A static PR preview, then push and create with approval; evidence hashes attached | `github_pr_create`, `github_pr_attach` |
| `sas` | SAS inventory, lineage with a verdict per step, a pandas draft that keeps SAS rules, parity checks | none |
| `onboarding` | Permitted Confluence/Word/PDF/Markdown exports, cited search, revocation, a guide with gaps marked | none |
| `browser` | An isolated Playwright lab, trace reading, failing selectors mapped to source, redacted evidence | `browser_lab_run` (downloads software) |
| `analytics` | Copilot and Claude Code usage with consent, observed vs estimated vs unknown, opt-out | none (`analytics_fetch` only reads) |

Each has a first-party **skill** (how to use it), an **agent** (drives it and stops for approval) and a **plugin**
(the server, skill and agent together) under the `neo-pragnya-mcp` namespace:

```bash
dex search mcp-kit
dex install neo-pragnya-mcp/jenkins-mcp-kit --target claude --scope project
```

## Register a server

```bash
dex mcp list                                   # servers, tools, which tools act
dex mcp config jenkins --client claude-code    # claude mcp add dex-jenkins -- uvx --from dex-trove==X dex mcp serve jenkins --root .
dex mcp config jenkins --client vscode         # .vscode/mcp.json entry (also: codex, json)
```

`config` only prints; it changes nothing. The printed command pins the Dex version you have.

## The rules every server follows

**Dry-run unless allowed and approved.** A tool that changes something outside your machine is refused unless the
server was started with `--allow-actions`. Even then it needs the `approval` digest from its preview: the sha256 of
the exact plan the preview showed. Change one parameter, or let the PR gain a commit, and the digest no longer
matches, so what runs is what a person saw. Every approval and refusal is appended to `.dex/mcp/audit.jsonl`.

**Credentials from the environment only** (`JENKINS_TOKEN`, `KIBANA_API_KEY`, `GH_TOKEN`...), never from arguments or
files. Results, logs and evidence are redacted (authorization headers, cookies, tokens in URLs, private keys,
secret-shaped strings). Plain `http://` is allowed only for a local test instance, and redirects to another host are
refused so credentials never travel.

**Inside the project.** Paths are resolved (symlinks too) and must stay under `--root`. The analytics server reads
Claude Code session logs only from the folder named in its consent.

**Evidence.** Every result has `status`, `artifacts` (path, media type, sha256, sensitivity, producer, schema),
`findings`, `warnings`, `provenance` and a `digest` that leaves timestamps out, so the same input gives the same
digest. Findings are also written as SARIF under `dex-evidence/<server>/`, where `ananke triage findings` reads them
(keep `dex-evidence/` out of `.gitignore` if you want Ananke to see it). Working state lives in `.dex/mcp/<server>/`.

**Documents are data.** Text read from exports, logs and traces is never treated as instructions; the onboarding
server flags text that tries.

## From the shell

Every tool can be called once without a client:

```bash
dex mcp call sas sas_lineage --args '{"paths": ["etl"]}'
dex mcp call kibana kibana_export --args '{"spec": "dashboards/checkout.json", "target_version": "8.14"}'
```

## What is verified, and what isn't yet

| Server | Verified | Not yet |
| --- | --- | --- |
| `jenkins` | Fake Jenkins and GitHub on 127.0.0.1: allowlist, parameters, crumb, auth, 401, idempotency, bounded polling | A real Jenkins |
| `kibana` | Field discovery, spec checks and the NDJSON contract on fixtures; import against a fake Kibana | Import into a real Kibana or OpenSearch Dashboards |
| `github` | A real git repository pushing to a local bare remote; a fake `gh` | github.com |
| `sas` | The draft runs on pandas 2 and 3 and matches hand-derived SAS results for a representative program | Output produced by SAS itself |
| `onboarding` | HTML, Word, Markdown and (through a fake `pdftotext`) PDF; injection, revocation, citations | A real Confluence space export |
| `browser` | A real Playwright 1.48.2 run with the installed Chrome: a healthy fixture page passed, a broken one failed; trace reading, mapping and redaction checked on those traces | A real application's test environment |
| `analytics` | A Copilot metrics export in the documented format, a fake metrics API, Claude Code session logs | A real organisation's metrics API |

The acceptance suite (`make acceptance-wheel`) drives the servers from the built wheel, including a stdio handshake
and refused actions.
