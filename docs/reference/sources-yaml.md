---
title: sources.yaml
description: The source map — every field, with examples.
---

# `sources.yaml`

`sources.yaml` at the repository root defines what Dex learns from. It is also shipped inside the wheel, so
`dex sources` works after installation.

```yaml
sources:            # learned (or learnable) sources, in priority order
  - id: …
candidates:         # repos evaluated but not mapped; shown on the Sources page
  - { repo: …, license: …, decision: …, offers: … }
```

## `sources[]`

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `id` | string | ✓ | Source id **and item namespace** (`<id>/<item>`). Lower-kebab; must satisfy Ananke's name rule. |
| `title` | string | | Display name (default: `id`) |
| `description` | string | | Shown on the Sources page |
| `adapter` | string | ✓ | `agent-skills`, `awesome-copilot` or `md-agents` |
| `repo` | URL | one of `repo`/`local` | Git URL to shallow-clone |
| `ref` | string | | Branch or tag to clone (default `HEAD`) |
| `local` | path | one of `repo`/`local` | Folder to read directly; relative to `sources.yaml`. Used when there is no `repo`, or with `--prefer-local`. |
| `homepage` | URL | | Link for sources without a public repo (first-party) |
| `enabled` | bool | | `false` → skipped by `dex learn` with no arguments (default `true`) |
| `options` | map | | Adapter options (below) |
| `exclude` | list of globs | | Files withheld from items, matched against paths relative to the source root (`fnmatch`) |
| `items` | map | | Per-item overrides keyed by item name: `title`, `inspired_by` |
| `license` | map | | `first_party`, `default`, `allow_review`, `expected` (below) |
| `notes` | string | | Free text for maintainers |

**Order is priority.** When two sources contain byte-identical entry files, the item from the earlier source wins
and the later one is excluded as `duplicate`.

### `license`

| Key | Meaning |
| --- | --- |
| `first_party: true` | We author this content. Allows `default` to apply when an item has no licence file. |
| `default: MIT` | Licence used for first-party items without their own licence file. **Ignored unless `first_party`.** |
| `allow_review: true` | Admit *review* licences (MPL, EPL, LGPL, CC-BY-SA) from this source. Record the decision in the PR. |
| `expected: …` | Documentation only: what we expect to find. Verdicts always come from the actual files. |

### `options` by adapter

| Adapter | Option | Default | Meaning |
| --- | --- | --- | --- |
| `agent-skills` | `roots` | `["."]` | Folders searched (recursively) for `SKILL.md`. Hidden folders are skipped except `.curated`, `.system`, `.experimental`. |
| `md-agents` | `globs` | `["agents/**/*.md"]` | Glob patterns for agent files (README/CONTRIBUTING/CHANGELOG ignored; `description` frontmatter required) |
| `md-agents` | `kind` | `agent` | Kind to assign |
| `awesome-copilot` | — | | Fixed layout: `skills/`, `agents/`, `instructions/`, `prompts/`, `hooks/`, `workflows/`, `plugins/` |

### `items`

```yaml
items:
  marvellous-aws-architecture-docs:
    title: Optional display title override
    inspired_by:
      - { title: AWS Reference Architecture Diagrams, url: "https://aws.amazon.com/architecture/reference-architecture-diagrams/" }
```

`inspired_by` appears in `dex show`, in `dex.json` and on the item page under **Inspired by**.

## Ignoring items without naming them here

`exclude` globs withhold *files* and are committed in this repo. To hide whole *items* without naming them in the
repo, put a `.dexignore` in the source's own root, or use the user-level `~/.config/dex-trove/ignore`. See
[First-party skills › Keeping personal skills private](../guides/first-party-skills.md#keeping-personal-skills-private).

## `candidates[]`

| Field | Meaning |
| --- | --- |
| `repo` | `owner/name` on GitHub |
| `license` | What was found (SPDX id or a short description) |
| `decision` | e.g. "Mapped — enable after size review", "Not importable until licensed" |
| `offers` | What the repo contains |

## Complete example

```yaml
sources:
  - id: neo-pragnya
    title: Neo Pragnya (first-party)
    adapter: agent-skills
    local: ../Skills
    homepage: https://github.com/Neo-Pragnya/Dex-Trove
    license: { first_party: true, default: MIT }
    exclude:
      - "marvellous-aws-architecture-docs/assets/icons/*.png"
    items:
      marvellous-aws-architecture-docs:
        inspired_by:
          - { title: "mingrammer/diagrams (MIT)", url: "https://github.com/mingrammer/diagrams" }

  - id: awesome-copilot
    title: Awesome GitHub Copilot
    adapter: awesome-copilot
    repo: https://github.com/github/awesome-copilot
    ref: main
    local: ../awesome-copilot
    license: { expected: MIT }

  - id: anthropic
    title: Anthropic Agent Skills
    adapter: agent-skills
    repo: https://github.com/anthropics/skills
    ref: main
    options: { roots: [skills] }

  - id: huggingface
    adapter: agent-skills
    repo: https://github.com/huggingface/skills
    enabled: false

candidates:
  - { repo: vercel-labs/agent-skills, license: "None found", decision: "Not importable until licensed", offers: "Vercel / Next.js skills" }
```
