---
title: First-party skills
description: Author skills for the neo-pragnya namespace, credit inspirations and withhold third-party assets.
---

# First-party skills

First-party items are authored by Neo Pragnya and live under the **`neo-pragnya`** namespace. In 0.1.2:

| Skill | What it does |
| --- | --- |
| [`marvellous-aws-architecture-docs`](https://neo-pragnya.github.io/Dex-Trove/skill/neo-pragnya.marvellous-aws-architecture-docs/) | AWS-reference-style architecture diagrams as code: animated SVGs with numbered flows, stage-by-stage views, draw.io and an interactive HTML docs page |
| [`astro-docs-site`](https://neo-pragnya.github.io/Dex-Trove/skill/neo-pragnya.astro-docs-site/) | Scaffold a pastel, interactive Astro documentation site for any repo (docs read from `docs/`, MkDocs nav import, Mermaid, callouts, Pages workflow, link checker). Used for this site and Ananke Plexus's |
| [`interactive-web-motion`](https://neo-pragnya.github.io/Dex-Trove/skill/neo-pragnya.interactive-web-motion/) | `motion-kit.js`: morphing SVG glyphs, a cursor-reactive shape field, rotating words, letter hover waves, particle text that diffuses from the cursor, reveals, count-ups, tilt and marching ants. Accessible and dependency-free |
| [`living-diagrams`](https://neo-pragnya.github.io/Dex-Trove/skill/neo-pragnya.living-diagrams/) | Diagrams that move with meaning: an orbit/plexus hero canvas, hover effects for any SVG or Mermaid diagram (connected nodes light up, pulses travel the edges), and animated terminal walkthroughs built from real command output |
| [`capability-acceptance`](https://neo-pragnya.github.io/Dex-Trove/skill/neo-pragnya.capability-acceptance/) | Behaviour-level acceptance tests and a release gate for any CLI or package: Gherkin scenarios in sandboxes, a capability catalog with blockers, PROMOTE / CONDITIONAL / BLOCK, adversarial probes with twins, wheel-under-test runs, browser journeys, and a scaffolder that discovers the CLI surface |
| [`package-security-scan`](https://neo-pragnya.github.io/Dex-Trove/skill/neo-pragnya.package-security-scan/) | Why a package gets quarantined by Black Duck-class scanners, and the fix with free tools: gitleaks, pip-audit, GuardDog and Bandit over the exact wheel and sdist, honest fixes for secrets, licences and code issues, and a blocking `dist-scan` release job |
| [`life-ikigai-architect`](https://neo-pragnya.github.io/Dex-Trove/skill/neo-pragnya.life-ikigai-architect/) | Personal Ikigai, vision, mission and roadmap as an animated HTML presentation |

## How they are learned

```yaml
- id: neo-pragnya
  adapter: agent-skills
  local: ../Skills                              # a sibling folder of this repo
  license: { first_party: true, default: MIT }
  exclude:
    - "marvellous-aws-architecture-docs/assets/icons/*.png"
    - "*/assets/previews/*"
```

`first_party: true` lets the `default` licence apply when a skill has no licence file. That is only legitimate
because we are the authors, so never set it for anyone else's content.

## Keeping personal skills private

The source folder can hold skills you **don't** want published. List them in a `.dexignore` file *in that folder*,
not in this repo, so their names never appear in Dex-Trove:

```gitignore
# ~/Documents/Repositories/Skills/.dexignore
# Personal skills — not for publication
my-private-skill
journal-*
```

Each line is an `fnmatch` pattern matched against the skill's name or its folder path. Matching items are skipped
**silently**. They are never copied, never listed in `EXCLUDED.json` or the lock, and only counted in the
terminal (`2 ignored (.dexignore)`). If an ignored skill was learned before, the next `dex learn` deletes it from the
trove.

To keep rules out of every folder, use a user-level file, `~/.config/dex-trove/ignore` (or `$DEX_TROVE_IGNORE`).
Prefix a line with a source id to scope it:

```text
neo-pragnya:my-private-skill     # only for this source
*:scratch-*                      # every source
experimental-*                   # unscoped = every source
```

> Removing an item from the trove does not remove it from git history. If a private item was ever committed, rewrite
> the history too (see the release guide's note on purging).

## Authoring a skill

1. Create `Skills/<name>/SKILL.md` with frontmatter:

   ```markdown
   ---
   name: my-skill                 # lower-kebab, matches the folder, ≤ 64 chars
   description: "What it does and when to use it — include the phrases people actually say."
   ---
   ```

2. Keep `SKILL.md` focused and move depth into `references/`, `scripts/` and `assets/` that the skill
   references explicitly.
3. If the skill uses third-party assets (icons, fonts, images), check their terms. If they can't be
   redistributed, add an `exclude` glob and a script that fetches them on demand.
4. Credit inspirations in `sources.yaml`:

   ```yaml
   items:
     my-skill:
       inspired_by:
         - { title: "Project that inspired it", url: "https://…" }
   ```

5. Learn and validate:

   ```bash
   dex learn neo-pragnya
   dex validate
   dex show neo-pragnya/my-skill
   ```

## Withheld assets: the AWS icons example

`marvellous-aws-architecture-docs` uses official AWS Architecture Icons. AWS licenses them for drawing
architecture diagrams, not for redistribution as an icon set, so Dex withholds `assets/icons/*.png` (and the
preview renders that embed them). The item records the fact in `notes`, the item page shows it, and users run the
skill's `scripts/fetch_icons.py`. That script downloads the icons from the MIT-licensed `diagrams` wheel. Until
then, `archlib` draws labelled boxes in their place.

## Re-learning in CI

`Skills/` is a local folder, not a git repo, so CI cannot re-learn it. The checked-in copy under
`trove/skills/neo-pragnya.*` is the record. Re-learn locally after changing a first-party skill, and commit the
result. Moving first-party skills into git is on the [roadmap](../design/CHECKLIST.md).
