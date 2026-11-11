---
name: kibana-dashboards
description: "Design Kibana (or OpenSearch Dashboards) dashboards from the fields an application really logs: find fields in mappings, JSON Schemas and Python/JS logging calls, check a dashboard spec for missing fields and type mismatches, export saved-object NDJSON for a target version, and import it into a test instance only on approval. Use for Kibana, ELK, OpenSearch dashboards, log metrics, saved objects or observability panels, even if they don't say MCP."
---

# Kibana dashboards from logged fields

This skill drives the **`dex-kibana`** MCP server that ships with Dex Trove (`dex mcp serve kibana`). The server runs
on your machine over stdio, uses only the Python standard library, and is dry-run by default: tools that change an
external system are refused unless the server was started with `--allow-actions`, and even then they need the
approval digest of the exact plan a person saw.

## Set it up

```bash
uv tool install dex-trove            # or: pipx install dex-trove
dex mcp config kibana --client claude-code    # prints: claude mcp add dex-kibana -- uvx --from dex-trove==… dex mcp serve kibana --root .
dex mcp config kibana --client vscode         # .vscode/mcp.json entry; also: codex, json
```

Add `--allow-actions` to the served command only in a session where actions are wanted.

.dex/kibana.json (targets only; production is refused):

```json
{"targets": {"test": {"url": "http://localhost:5601", "environment": "test", "space": "default", "flavor": "kibana"}}}
```

A dashboard spec in the project, e.g. `dashboards/checkout.json`:

```json
{"title": "Checkout health", "data_view": {"title": "logs-app-*", "time_field": "@timestamp"},
 "panels": [{"title": "Errors over time", "type": "line", "filter": "log.level:error"},
            {"title": "Average latency", "type": "metric", "metric": {"agg": "avg", "field": "duration_ms"}},
            {"title": "Requests by route", "type": "bar", "split": {"field": "http.route", "size": 5}}]}
```

Environment for import: `KIBANA_API_KEY`, or `KIBANA_USER` and `KIBANA_PASSWORD`.

## Tools

| Tool | What it does |
| --- | --- |
| `kibana_fields` | Fields the application logs or maps, with types (declared, inferred or unknown) and where each comes from. |
| `kibana_spec` | Checks a dashboard spec against the logged fields: missing fields, type mismatches, unverified types. |
| `kibana_export` | Writes saved-object NDJSON for the target Kibana version and checks its contract. Imports nothing. |
| `kibana_import_preview` | What an import would send where, the target's version, and an approval digest. Sends nothing. |
| `kibana_import` | Imports the previewed NDJSON into a non-production target, never overwriting. Needs --allow-actions and the approval digest the user accepted. |

## How to use it

1. `kibana_fields`: every logged or mapped field with its type and source (declared, inferred, unknown) and conflicts.
2. Write the spec with fields from that list. Panel types: metric, line, bar, area, table, pie; aggregations: count, sum, avg, min, max, median, cardinality.
3. `kibana_spec spec`: missing fields, numeric aggregations on non-numeric fields, text fields used for splits.
4. `kibana_export spec target_version`: NDJSON (data view, visualizations, dashboard) with a contract check; stable ids, so reruns give the same file.
5. Optional: `kibana_import_preview ndjson target`, then `kibana_import ... approval` with `--allow-actions`. Never overwrites.

## Rules

- Never import into a production target; export the NDJSON for the change process instead.
- Fix missing fields at the source (log them or map them) rather than exporting with allow_missing_fields.
- Credentials come from the environment only. Results, logs and evidence are redacted.
- Every result has the same envelope: `status`, `artifacts` (with sha256), `findings`, `warnings`, `provenance` and a
  `digest` that ignores timestamps. Findings are also written as SARIF under `dex-evidence/kibana/`, where
  `ananke triage findings` reads them.
- Every action, approved or refused, is appended to `.dex/mcp/audit.jsonl`.

## What has been verified

Field discovery, spec checks and the NDJSON contract are tested on fixtures; the import is tested against a fake Kibana (kbn-xsrf, API key, multipart, conflicts). The export targets the 7.10 saved-object format that Kibana migrates forward, but no import into a real Kibana or OpenSearch Dashboards has been recorded yet.

From the shell, the same tools run once with `dex mcp call kibana <tool> --args '{...}'`.
