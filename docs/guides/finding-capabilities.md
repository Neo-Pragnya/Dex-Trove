---
title: Finding capabilities
description: How Dex Trove classifies every item by task, methodology, phase, role and more, why it uses typed facets instead of tags, and how filtering works in the CLI and on the site.
---

# Finding capabilities

With almost a thousand items in the trove, a name search often isn't enough. "I need something to help a QA engineer
test an API, test-first, in Python" is a question about *what an item does, who it's for and how you work*. Dex Trove
answers it with **typed facets**: separate, controlled dimensions such as task, methodology, lifecycle phase and role.
You filter on them the same way in the CLI and on the [catalog](https://neo-pragnya.github.io/Dex-Trove/catalog/).

```bash
dex search --task write-tests --methodology tdd --role qa-engineer --language python --explain
```

## Why not just tags?

Upstream items carry tags, but a tag list can't tell *what an item is* from *what it does*, *when it's useful* or *who
uses it*. In this trove:

- Upstream tags have **341 distinct values, and 247 of them appear only once**. They're different authors' words, not
  a shared vocabulary.
- Only **3** items are tagged `testing`, yet **113** items are about writing tests.
- `python` could mean "written in Python", "for Python code" or "needs Python installed". `adlc` and `sdlc` look
  alike but mean different things.

Facets fix this with one question per dimension, a fixed list of values, a definition for every value, and a record of
**where each value came from**.

## The facets

| Facet | Question | Example values | How it's filled |
| --- | --- | --- | --- |
| `kind` | What is it? | skill, agent, instruction, workflow, hook, plugin | From the catalog |
| `task` | What job does it do? | write-tests, review-code, debug, write-spec, design-architecture | Curation, tags, text rules |
| `methodology` | Which way of working? | sdlc, adlc, sdd, tdd, bdd, devops, sre | Curation, tags, text rules |
| `phase` | Where in the lifecycle? | discovery, requirements, design, implementation, testing, verification, deployment, operations | Curation, text rules |
| `role` | Who uses it? | developer, qa-engineer, architect, security-engineer, devops-engineer | Curation, text rules |
| `domain` | Which part of a system? | api, frontend, backend, infrastructure, data, ml-ai, security | Curation, tags, text rules |
| `language` | Which language? | python, typescript, csharp, java, go, sql | Curation, tags, `applyTo` globs, text rules |
| `framework` | Which technology? | pytest, playwright, react, terraform, mcp, azure | Curation, tags, text rules |
| `platform` | Where can Dex install it? | claude-code, github-copilot, ananke | From the install layout |
| `maturity` | How established? | stable, beta, experimental, deprecated, unknown | Curation (most upstream items: `unknown`) |

Every value, its definition and its aliases are in the [taxonomy reference](../reference/taxonomy.md), or run
`dex facets list` (and `dex facets list methodology` for one facet).

**Facets are independent.** A skill can be `task: write-tests`, `methodology: tdd, adlc` and `phase: testing,
implementation` at the same time. Task says what it does, methodology how you work, phase when, and role who. Keeping
them separate is what lets you combine them precisely.

### SDLC, ADLC and the other methodologies

Methodologies describe *ways of working*, not artifacts:

- **SDLC**: the human-driven loop of requirements, design, build, test, release and operate.
- **ADLC**: the *Agent Development Life Cycle*, as [Ananke Plexus](https://neo-pragnya.github.io/Ananke-Plexus/) uses
  it. Agents and humans build software together, driven by specs, policies, explicit context assembly, gates and
  execution evidence.
- **SDD, TDD, BDD, ATDD, DDD** are practices that can live inside either lifecycle.
- **DevOps, SRE, MLOps, DataOps** are operating models.

SDLC and ADLC overlap, but they're **not aliases**: the taxonomy refuses to merge them. Many good skills serve both,
and say so.

Methodology is the sparsest facet: only 61 of 964 items say which method they support, because most upstream
authors don't. That's an honest gap, not a bug. Use methodology together with task or phase, not on its own.

## Where facet values come from

Dex never edits upstream files. Facets are a **sidecar**, `trove/facets.json`, rebuilt by `dex learn` and
`dex facets build`. Each value comes from one of four sources, in this order of precedence:

1. **Curated**: reviewed by a maintainer in [`taxonomy/curation.yaml`](https://github.com/Neo-Pragnya/Dex-Trove/blob/main/src/dex_trove/taxonomy/curation.yaml).
   These are marked *approved*. The first-party skills and the core method skills (superpowers, Anthropic) are
   curated.
2. **Native**: the item's own metadata: upstream tags that clearly mean a facet value, and `applyTo` globs (an
   instruction for `**/*.py` is `language: python`).
3. **Rules**: patterns in the taxonomy matched against the item's name, title, description and tags. Each hit records
   the text it matched. These are marked *review-pending*.
4. **Derived**: facts Dex knows itself: `kind` from the catalog, `platform` from where `dex install` can put the item.

For each facet, the first source that has any value wins. The others are kept, so a reviewer can see what curation
overrode. Today 25 items are curated and 939 are review-pending.

See it for any item:

```console
$ dex facets show awesome-copilot/playwright-python
instruction:awesome-copilot/playwright-python  review-pending (rules)
  kind         instruction  ← derived: catalog: kind
  task         write-tests  ← rules: write-tests: title: 'Test'
  phase        testing  ← rules: testing: title: 'Test'
  role         qa-engineer  ← rules: qa-engineer: title: 'Test'
  language     python  ← rules: python: name: 'python'
  framework    playwright  ← rules: playwright: name: 'playwright'
  platform     ananke, github-copilot  ← derived: catalog: install layout
  maturity     unknown  ← derived: unknown: no maturity metadata
```

Item pages on the site show the same facets under **Where it fits**, marked as reviewed or as suggested.

## How a filter is evaluated

The rules are deliberately simple, so a result is always explainable:

- **Any value within a facet; all facets together.** `--language python --language typescript --role qa-engineer`
  means (python *or* typescript) *and* qa-engineer. On the site, picking two chips in one facet widens the results,
  and picking a chip in another facet narrows them.
- **`--strict`** requires *every* listed value within a facet: `--task write-tests --task plan-tests --strict` returns
  only items that do both.
- **`--not facet=value`** excludes items, for example `--not maturity=deprecated`.
- **Missing metadata never matches.** An item with no methodology isn't returned for `--methodology adlc`. Dex doesn't
  guess "probably ADLC".
- **Filter first, rank second.** Ranking only orders the items that passed. It never adds an item a filter excluded,
  and never quietly drops a filter.
- **Counts show what a choice would give.** The number next to each value ignores that facet's own selection, so it
  tells you how many items you'd see if you picked it (disjunctive counting).
- **No results, no guessing.** An empty result tells you which filter to drop:

  ```console
  $ dex search --methodology adlc --role qa-engineer --phase verification --task generate-api-tests --language python
  No items match every filter.
    without the task filter: 1 item(s)
    without the methodology filter: 0 item(s)
    ...
  ```

- **Unknown values are errors.** A typo is never silently ignored:

  ```console
  $ dex search --methodology waterfall
  'waterfall' is not a methodology term; choose from: adlc, atdd, bdd, dataops, ddd, devops, mlops, sdd, sdlc, sre, tdd
  ```

- **Aliases work.** `--role test-engineer` means `--role qa-engineer`; `--methodology test-driven-development`
  means `tdd`.

### Ranking

Among items that pass, Dex scores how *fully* each matches. For each facet in the query, it takes the share of
selected values the item carries, then weights it: task 0.30, methodology 0.20, phase 0.15, role 0.10, context
(domain, language, framework, platform) 0.10, and reviewed status 0.10. A curated item scores 1.0 on that last part
and a review-pending item 0.5. The score is normalised over the parts the query uses. Ties go to the better text match
(when you give words), then the id. These weights are starting points, not measured truths; `--explain` shows each
item's contributions.

## Using it

### In the CLI

```bash
dex facets list                         # every facet and value, with counts
dex facets list role                    # one facet
dex search --methodology tdd --phase testing --explain
dex search "api" --role qa-engineer --not maturity=deprecated
dex search --task review-code --language python --json      # for scripts
dex search --framework terraform -n 10 --cursor 10           # the next page
dex facets show superpowers/systematic-debugging             # one item's facets and evidence
```

`dex search <words>` with no facet options works exactly as before. With facets, `--json` returns the results, each
one's facets and score, the next-page cursor, the facet counts and, for an empty result, the relaxation counts.

### On the site

The [catalog](https://neo-pragnya.github.io/Dex-Trove/catalog/) has a **Narrow by what you're doing** panel: one
group per facet, with a count on every value. Choices are kept in the URL (`/catalog/?methodology=tdd&phase=testing`),
so a filtered view can be bookmarked or shared. Every chip on an item page links to the catalog filtered by that
value.

## What facets can't tell you

Facets say where an item is **relevant**. They don't prove it will **run** in your setup. Whether it can run
depends on typed inputs and outputs, declared requirements, the tools you have installed, and your policy. Ananke
checks those when it resolves and locks a capability. Related ideas:

- A shared tag or facet doesn't make two items compatible. Two `write-tests` skills may expect completely different
  frameworks.
- Trust and licence aren't facets you can edit. Licence comes from evidence (see the [licence policy](../concepts/licence-policy.md)),
  and trust is decided by the harness that runs the item.
- Rule-based values are suggestions. They're good enough to narrow a search, and every one shows its evidence, but
  only curated values are reviewed.

## Improving the facets

- **Curate an item.** Add an entry to `src/dex_trove/taxonomy/curation.yaml` with the facet values and a one-line
  `evidence` note, then run `dex facets build` and `dex validate`. Curated values must be taxonomy terms; anything
  else fails the build.
- **Change the vocabulary.** Edit `src/dex_trove/taxonomy/ontology.yaml`. New terms need a definition. Renamed terms
  stay as `deprecated: true` with `replaced_by`, so old queries keep working. Bump `taxonomy_version`, then run
  `dex facets doc` to regenerate the [reference page](../reference/taxonomy.md).
- **Unmapped upstream tags** are kept on each record (`unmapped.tags`) for review, not discarded. 72 items have some
  today. They're the best source of new aliases.

`dex validate`, and the release gate, fail if `facets.json` is stale, a curated value isn't a term, or the taxonomy
breaks its own rules (duplicate ids, an alias claimed by two values, SDLC and ADLC merged).
