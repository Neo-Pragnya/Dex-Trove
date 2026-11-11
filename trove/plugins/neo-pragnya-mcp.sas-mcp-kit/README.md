# SAS to Python with parity

Installs the `dex-sas` MCP server (from the `dex-trove` package), the [`sas-to-python`](../../skills/sas-to-python/SKILL.md) skill and the [`sas-modernizer`](../../agents/sas-modernizer.agent.md) agent.

The server is dry-run by default. To allow approved actions, change the server's args to end with `--allow-actions` in a session where you want them.

## What has been verified

The generated draft runs on pandas 2 and pandas 3 and matches hand-derived SAS results for a representative program (DATA step with ELSE IF chains, DELETE, WHERE and missing values; SORT NODUPKEY; MEANS NWAY; FREQ). No comparison with output produced by SAS itself has been recorded yet.
