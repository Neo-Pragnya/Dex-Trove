---
name: skill-safety-lab
description: "Check a skill, agent, hook or plugin before installing or publishing it: what it can do (network, processes, file writes, secrets, privilege, piped installers, hooks, MCP servers) with the line for each, what it costs in tokens, whether search finds it for the right prompts and not the wrong ones, and what changed since an older copy. Use for skill review, agent security, plugin vetting, 'is this skill safe', skill quality or before publishing to a catalog."
---

# Skill safety and effectiveness lab

Uses `dex lab`, which reads the item's files and runs none of them.

## Steps

1. Check one item: `dex lab namespace/name`. The verdict is *block* (a script pipes a download into a shell, or
   a credential is embedded), *review* (it can reach the network, start processes, write files, read secrets,
   tells the reader to pipe an installer into a shell, or gained a permission) or *publishable*.
2. Measure whether it's found. Write prompts that should find it and some that shouldn't:

   ```json
   [{"prompt": "migrate our SAS programs to pandas", "expect": true},
    {"prompt": "tune a pandas groupby", "expect": false}]
   ```

   `dex lab namespace/name --cases cases.json` reports recall in the top three, false triggers and accuracy.
   Fix a low recall or a false trigger by rewriting the description, then measure again.
3. Compare with the previous copy before publishing a change: `dex lab namespace/name --against old-copy/`.
   A permission it gained is a reason to look closely.
4. For the whole catalog: `dex lab --survey` gives verdicts, how many items have each permission and the
   always-loaded token cost.

## Rules

- *Review* isn't *bad*: a deploy skill must reach the network. Check that each permission matches what the item
  says it does.
- Never publish an item with a *block* verdict.
