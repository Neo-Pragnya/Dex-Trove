# Skill lab

`dex lab` checks a skill, agent, hook or plugin before you install or publish it. It reads the item's files and runs
none of them.

```bash
dex lab neo-pragnya-mcp/sas-to-python                       # what it can do and what it costs
dex lab neo-pragnya-mcp/sas-to-python --cases cases.json    # and whether search finds it for the right prompts
dex lab namespace/name --against ./older-copy               # and what changed since an older copy
dex lab --survey                                            # the whole catalog
```

## What it reports

- **Permissions**, each with the file and line it was read from: `network`, `process` (starting programs or
  evaluating code), `writes-files`, `reads-secrets` (environment, keyring, credential files), `privilege` (sudo,
  setuid), `registers-hooks`, `registers-mcp-server`, `instructs-remote-exec` (documentation telling the reader to pipe
  a download into a shell), and two that block: `remote-exec` (a script that does it) and `embedded-credential`.
- **Token cost**: always loaded (the description an assistant reads to decide whether to use the item), on activation
  (the entry file) and everything the item ships, at four characters per token.
- **Effectiveness**, from your cases: recall (prompts that should find the item rank it in the top three of Dex's own
  search), false triggers (prompts that shouldn't, but do) and accuracy. Without cases it says *unknown*.
- **Regressions** against an older copy: permissions gained or lost, and how each cost changed.

## Verdicts

| Verdict | When |
| --- | --- |
| `block` | A script pipes a download into a shell, or a credential is embedded. `dex lab` exits 1 |
| `review` | It can reach the network, start processes, write files, read secrets or escalate privilege; registers hooks or MCP servers; tells the reader to pipe an installer into a shell; gained a permission; or is found for under 80% of its cases or for a prompt it shouldn't be |
| `publishable` | None of those |

*Review* isn't *bad*: a deployment skill has to reach the network. The question is whether each permission matches
what the item says it does.

## The catalog today

`dex lab --survey` over the 1,735 items in this release: 1,347 publishable, 388 to review, none blocked. 13 items'
documentation tells the reader to pipe an installer into a shell (for example the Azure CLI or Hugging Face CLI
install lines); they're `review`, not `block`, because nothing runs them, but an assistant following them might. The
median always-loaded description costs 57 tokens, the largest 267.

For `sas-to-python`, five SAS migration prompts all found it (recall 1.0), and of three unrelated prompts one,
"tune a pandas groupby for performance", ranked it third: a false trigger worth fixing in its description.
