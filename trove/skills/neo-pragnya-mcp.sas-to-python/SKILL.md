---
name: sas-to-python
description: "Move SAS programs to Python with evidence: inventory DATA steps, PROCs, PROC SQL and macros, map dataset lineage with a supported/partial/unsupported verdict per step, write a pandas draft that keeps SAS missing-value and sorting rules, and prove outputs match SAS within a declared tolerance. Use for SAS migration, modernization, SAS to pandas or Python, SAS lineage or reconciling SAS outputs, even if they don't say MCP."
---

# SAS to Python with parity

This skill drives the **`dex-sas`** MCP server that ships with Dex Trove (`dex mcp serve sas`). The server runs
on your machine over stdio, uses only the Python standard library, and is dry-run by default: tools that change an
external system are refused unless the server was started with `--allow-actions`, and even then they need the
approval digest of the exact plan a person saw.

## Set it up

```bash
uv tool install dex-trove            # or: pipx install dex-trove
dex mcp config sas --client claude-code    # prints: claude mcp add dex-sas -- uvx --from dex-trove==… dex mcp serve sas --root .
dex mcp config sas --client vscode         # .vscode/mcp.json entry; also: codex, json
```

Add `--allow-actions` to the served command only in a session where actions are wanted.

No configuration. The draft needs pandas where it runs (not in Dex): `uv run --with pandas python sas_draft.py --data in --out out`.

## Tools

| Tool | What it does |
| --- | --- |
| `sas_inventory` | SAS steps, datasets read and written, macros, %let values, libnames and %includes, with lines. |
| `sas_lineage` | Dataset-to-step lineage and a supported/partial/unsupported verdict for every step, with reasons. |
| `sas_draft` | Writes a pandas draft that keeps SAS missing-value rules; untranslated steps stop the run. |
| `sas_parity` | Compares a SAS output CSV with the draft's output within a tolerance, by key or by position. |

## How to use it

1. `sas_inventory paths`: steps with lines, datasets read and written, macros, `%let`, libnames, `%include`.
2. `sas_lineage`: dataset-to-step edges, a Mermaid diagram and a verdict per step with reasons (SARIF for partial and unsupported).
3. `sas_draft output`: a pandas draft. Every statement cites its SAS line; helpers keep SAS rules (missing is smallest, `.` = `.`, SUM skips missing, half-away rounding, stable sort). Untranslated steps stop the run unless `--skip-unsupported`.
4. Export SAS outputs to CSV, run the draft on the same inputs, then `sas_parity expected actual keys abs_tol plan` for each output.

## Rules

- Never describe a partial or unsupported step as equivalent: show its reasons.
- Macros are quarantined: translate them by hand, then prove the result with parity.
- Declare the tolerance with the owner of the numbers before comparing.
- Credentials come from the environment only. Results, logs and evidence are redacted.
- Every result has the same envelope: `status`, `artifacts` (with sha256), `findings`, `warnings`, `provenance` and a
  `digest` that ignores timestamps. Findings are also written as SARIF under `dex-evidence/sas/`, where
  `ananke triage findings` reads them.
- Every action, approved or refused, is appended to `.dex/mcp/audit.jsonl`.

## What has been verified

The generated draft runs on pandas 2 and pandas 3 and matches hand-derived SAS results for a representative program (DATA step with ELSE IF chains, DELETE, WHERE and missing values; SORT NODUPKEY; MEANS NWAY; FREQ). No comparison with output produced by SAS itself has been recorded yet.

From the shell, the same tools run once with `dex mcp call sas <tool> --args '{...}'`.
