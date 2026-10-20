---
title: Why Dex Trove
description: The problem Dex Trove solves and the principles behind it.
---

# Why Dex Trove

## The problem

Agent harnesses such as Claude Code, GitHub Copilot and Ananke Plexus become far more capable with good
*artifacts*: a skill that knows how to build a draw.io diagram, an agent that reviews Terraform, an instruction
file that encodes a team's Python conventions. The community has produced thousands of them. Using them safely is
harder than it looks:

1. **They are scattered.** Each repo has its own layout: `skills/*/SKILL.md`, `agents/*.agent.md`,
   `instructions/*.instructions.md`, `plugins/*/plugin.json`, hooks with `hooks.json`, agentic workflows with
   `on:` triggers.
2. **Licences are inconsistent and often wrong at repo level.** On 2026-10-19:
   - `anthropics/skills` had **no repo licence**. Its example skills carry Apache-2.0 files; its document skills
     carry proprietary, source-available terms.
   - `ComposioHQ/awesome-claude-skills` **redistributes** those proprietary skills.
   - `vercel-labs/agent-skills` had no licence anywhere, so nothing in it may be redistributed.
   - Even well-run awesome-copilot has items that say `license: Complete terms in LICENSE.txt`.
3. **Copying content creates obligations.** MIT and BSD require keeping the copyright notice; Apache-2.0 requires
   shipping the licence text (§4a) and any `NOTICE`. Copying blindly into a package published on PyPI is
   *distribution*, and silently dropping those obligations is a licence violation.
4. **Harnesses need structure.** Ananke's registry wants a strict manifest (kind, namespace, SemVer, licence,
   permissions, provenance) for every artifact, not a loose folder.

## What Dex Trove does

Dex Trove turns that mess into one installable, governed library:

| Step | What happens |
| --- | --- |
| **Map** | Upstream repos are listed in `sources.yaml` with an adapter that understands their layout |
| **Learn** | `dex learn` fetches each source at a pinned commit and finds its items |
| **Admit** | Each item's licence is resolved from the licence *text* (item → folder → repo); only redistributable licences pass |
| **Guard** | Size, symlinks, real credentials, duplicates, executable content |
| **Normalise** | Upstream bytes are copied **verbatim**, with an `ananke.yaml`, a `dex.json` provenance record and the governing licence text added alongside |
| **Ship** | A reviewed PR, then PyPI (`dex-trove`) and this documentation site |

## Principles

**Unknown means out.** No licence, an unrecognised licence or restrictive terms anywhere in an item excludes it.
Every exclusion is recorded with evidence in `trove/EXCLUDED.json` and on the [Excluded](https://neo-pragnya.github.io/Dex-Trove/excluded/) page.

**Most specific evidence wins.** A repo's licence describes the repo's own work. A licence file inside an item
describes that item. Dex resolves from the item outwards.

**Never modify upstream bytes.** Copies are byte-for-byte, so copyright notices stay intact, re-learn diffs are
honest, and `dex validate` can prove nothing drifted.

**Credit is a feature.** Every item page links to its exact upstream path at the learned commit. First-party
skills list what inspired them. The [Sources & inspirations](https://neo-pragnya.github.io/Dex-Trove/sources/) page lists every repo we learn
from, and every repo we evaluated and didn't.

**Harness-native, harness-agnostic.** Items ship as Ananke manifests *and* install natively into Claude Code and
Copilot. The library is useful whichever harness you run.

**Reviewable by humans.** Learning produces a diff of `trove/`, which is reviewed in a pull request like code.
A licence that changes upstream shows up as an item moving into `EXCLUDED.json`.

## How it relates to awesome-copilot

[github/awesome-copilot](https://github.com/github/awesome-copilot) is the primary inspiration and the largest
source. It is a *community catalog* for one tool. Dex Trove is a *governed package* across tools:

| | awesome-copilot | Dex Trove |
| --- | --- | --- |
| Content | Authored in the repo | Learned from many repos plus first-party |
| Licence | One repo licence (MIT), item exceptions noted in frontmatter | Resolved per item from text; denied items excluded |
| Distribution | Git clone / Copilot plugin marketplace | `pip install dex-trove`, Ananke registry, native installers |
| Format | Copilot-native | Upstream format **plus** Ananke manifest and provenance |
| Website | Astro, page per resource | Astro, page per item with licence evidence and provenance |

## How it relates to Ananke Plexus

Ananke Plexus already *can* learn from a repo (`ananke registry learn ./awesome-copilot`). Dex Trove adds the
parts a harness shouldn't have to own:

- **Curation across sources**, with duplicate detection and priority.
- **Licence admission before distribution.** Ananke's licence policy then applies on top, as defence in depth.
- **A versioned, signed-off snapshot.** A given `dex-trove` version is a fixed set of items at fixed commits.
- **Offline availability.** Everything is in the wheel; no network is needed at install time.

See [Ananke integration](../guides/ananke-integration.md).
