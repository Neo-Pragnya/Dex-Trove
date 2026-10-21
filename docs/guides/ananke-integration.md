---
title: Ananke integration
description: Load the trove into an Ananke Plexus registry — all of it, or a curated slice.
---

# Ananke integration

Dex Trove is designed to be loaded into [Ananke Plexus](https://github.com/Neo-Pragnya/Ananke-Plexus). Every item
ships a strict Ananke manifest (`ananke.yaml`) inside the wheel, so Ananke can discover and register the whole
library with no glue code.

## Recommended: switch it on with `[troves]` (Ananke 0.3.7+)

```bash
pip install "ananke-plexus[dex]"        # Ananke + Dex Trove
cd my-project && ananke init
ananke registry troves list              # [off] dex-trove  dex-trove 0.1.3  972 items
ananke registry troves enable dex-trove --kind skill --kind agent   # writes [troves.dex-trove]
ananke registry troves sync              # learns that slice; secret-flagged items are skipped
```

```toml
# .ananke/config.toml (written by `troves enable`, safe to edit)
[troves.dex-trove]
enabled = true
kinds = ["skill", "agent"]      # empty = every kind
namespaces = []                 # e.g. ["neo-pragnya"]
include_flagged = false
```

Re-run `ananke registry troves sync` after `pip install -U dex-trove`: unchanged items stay as they are, and changed
ones get a new version. Ananke finds any trove through the `ananke.troves` entry point, so Dex needs no other glue.
The options below remain for one-off loads and older Ananke versions.

## Option A: learn the installed package (everything)

```bash
pip install ananke-plexus dex-trove
cd my-project
ananke registry init
ananke registry learn python:dex-trove
```

Ananke's static Python importer reads the wheel's `RECORD`, finds every `ananke.yaml` up to four path parts deep
(`dex_trove/<kind>/<ns.name>/ananke.yaml`) and registers each item as an immutable version. It never imports
the package.

Expected result for 0.1.0: **961 registered, 9 refused** by Ananke's secret scanner (the
[flagged items](../concepts/security-model.md#why-two-secret-scanners)), so the command exits `1`. Either accept
that, or use option B, which skips them.

## Option B: `dex ananke sync` (filtered, clean exit)

```bash
dex ananke sync --project .                                   # all items except secret-flagged ones
dex ananke sync --project . --kind skill --kind agent         # only skills and agents
dex ananke sync --project . --source neo-pragnya              # only first-party
dex ananke sync --project . --name superpowers/systematic-debugging --name git-commit
dex ananke sync --project . --dry-run                         # report, register nothing
dex ananke sync --project . --include-flagged                 # also offer flagged items
```

`dex ananke sync` selects items from the catalog, stages them in a temporary directory and runs
`ananke registry learn <dir> --project <project>`. The `ananke` CLI is the contract: Dex never writes Ananke's
registry directly. Use `--ananke-bin` if `ananke` isn't on `PATH`.

A full sync of 0.1.0 registers 961 items and exits `0`. Re-running it is idempotent: unchanged items are reported
as `skipped`.

## What Ananke receives

```yaml
# trove/skills/awesome-copilot.git-commit/ananke.yaml
kind: skill
namespace: awesome-copilot
name: git-commit
version: 1.0.0
ananke_id: urn:dex-trove:skill:awesome-copilot:git-commit
summary: Execute git commit with conventional commit message analysis, intelligent staging, and message generation.
  Use when user asks to commit changes, create a git commit, or mentions "/commit".
description: '…'
runtime:
  supported: [claude-code, github-copilot, generic]
permissions: {filesystem: {read: [], write: []}, shell: {allow: []}, network: []}
license: {expression: MIT, source: "frontmatter license: 'MIT'", approval: approved}
metadata:
  tags: [awesome-copilot, skill]
  homepage: https://github.com/github/awesome-copilot/tree/613efc8c…/skills/git-commit
  repository: https://github.com/github/awesome-copilot
```

| Dex kind | Ananke kind | Extra manifest fields |
| --- | --- | --- |
| skill | `skill` | |
| agent | `agent` | `instructions.ref` → entry file |
| instruction, prompt | `prompt` | `instructions.ref` → entry file |
| hook | `tool` | no `permissions` (code-bearing: Ananke warns until reviewed) |
| workflow | `workflow` | |
| plugin | `bundle` | `members: [{ref: ananke://<kind>/<ns>/<name>, version: '*'}]` |

Items that contain no code declare empty permissions explicitly. Items with scripts leave `permissions` unset, so
Ananke's `missing-permissions` warning prompts a review before promotion.

## After registration

```bash
ananke registry search debugging
ananke registry show superpowers/systematic-debugging
ananke registry resolve awesome-copilot/arize-ax --explain     # bundle → 9 member skills
ananke apm install superpowers/systematic-debugging --activate
ananke registry promote superpowers/systematic-debugging --trust approved --reviewed-by you
```

Items arrive as trust `discovered` in channel `candidate`. Promotion and trust remain local decisions in each
Ananke project.

## Tightening policy

Ananke's registry policy applies on top of Dex's licence admission:

```toml
# .ananke/registry/policy.toml
[licenses]
allow = ["MIT", "Apache-2.0"]     # refuse everything else at registration
allow_unknown = false

[permissions]
forbid = ["shell.execute"]

[secrets]
mode = "reject"                   # default; flagged items stay out
```

## Upgrading

```bash
pip install -U dex-trove
ananke registry learn python:dex-trove     # registers new versions only for items whose content changed
ananke apm upgrade --dry-run
```
