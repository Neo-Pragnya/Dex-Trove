---
title: Getting started
description: Install dex-trove, find an item, inspect its provenance and install it.
---

# Getting started

## Requirements

- Python **3.11+**
- Optional: [Ananke Plexus](https://github.com/Neo-Pragnya/Ananke-Plexus) (`pip install ananke-plexus`), Claude
  Code, or GitHub Copilot

## Install

```bash
pip install dex-trove          # or: uv tool install dex-trove   /   pipx install dex-trove
dex --version                  # dex-trove 0.1.0
```

The whole library (964 items) is inside the wheel. No network access is needed after installation.

## Find something

```bash
dex search terraform review
dex search diagram --kind skill -n 10
dex list --source neo-pragnya
dex list --kind plugin --json
```

Search is weighted (name > title > tags > description), and every word must match. You can also browse the
[catalog](https://neo-pragnya.github.io/Dex-Trove/catalog/) on the website, where each item has its own page.

## Inspect before you install

```bash
dex show neo-pragnya/marvellous-aws-architecture-docs
```

```text
Marvellous AWS Architectures Docs  (skill:neo-pragnya/marvellous-aws-architecture-docs@1.0.0)
Marvellous AWS Architectures Docs: build AWS-reference-style architecture diagrams as code …
source:   Neo Pragnya (first-party) — https://github.com/Neo-Pragnya/Dex-Trove/tree/main/trove/skills/…
licence:  MIT (first-party default (sources.yaml))
inspired: AWS Reference Architecture Diagrams https://aws.amazon.com/architecture/reference-architecture-diagrams/
inspired: mingrammer/diagrams (MIT) https://github.com/mingrammer/diagrams
files:    README.md, SKILL.md, assets/examples/concept_cards.py, …
path:     …/site-packages/dex_trove/skills/neo-pragnya.marvellous-aws-architecture-docs
```

`dex show --json` prints the full `dex.json` record ([item format](../reference/item-format.md)).

## Install

```bash
# Claude Code, for your user (~/.claude/skills/systematic-debugging/)
dex install superpowers/systematic-debugging --target claude

# Claude Code, for this project only (./.claude/…)
dex install anthropic/mcp-builder --target claude --scope project

# GitHub Copilot, for this repository (./.github/skills/git-commit/)
dex install awesome-copilot/git-commit --target copilot

# A whole plugin: every member skill and agent
dex install awesome-copilot/arize-ax --target copilot

# Anywhere, keeping the full normalised item (including ananke.yaml and dex.json)
dex install anthropic/canvas-design --target dir --path ./vendor
```

See [Installing items](installing-items.md) for where each kind goes and what each tool does with it.

## References

Wherever a command takes `REF`, you can write:

| Form | Example |
| --- | --- |
| `namespace/name` | `awesome-copilot/git-commit` |
| bare `name` (if unique) | `git-commit` |
| `kind:namespace/name` | `skill:awesome-copilot/git-commit` |

If a bare name is ambiguous, `dex` lists the candidates.

## With Ananke

```bash
pip install ananke-plexus
ananke registry init
ananke registry learn python:dex-trove        # everything
# or a slice:
dex ananke sync --kind skill --source superpowers
ananke registry search debugging
```

See [Ananke integration](ananke-integration.md).

## Next steps

- Understand [what each kind is](../concepts/artifact-kinds.md).
- Read [why an item is or isn't included](../concepts/licence-policy.md).
- Contribute a [new source](adding-a-source.md) or a [first-party skill](first-party-skills.md).
