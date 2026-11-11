# Kibana dashboards from logged fields

Installs the `dex-kibana` MCP server (from the `dex-trove` package), the [`kibana-dashboards`](../../skills/kibana-dashboards/SKILL.md) skill and the [`kibana-dashboard-builder`](../../agents/kibana-dashboard-builder.agent.md) agent.

The server is dry-run by default. To allow approved actions, change the server's args to end with `--allow-actions` in a session where you want them.

## What has been verified

Field discovery, spec checks and the NDJSON contract are tested on fixtures; the import is tested against a fake Kibana (kbn-xsrf, API key, multipart, conflicts). The export targets the 7.10 saved-object format that Kibana migrates forward, but no import into a real Kibana or OpenSearch Dashboards has been recorded yet.
