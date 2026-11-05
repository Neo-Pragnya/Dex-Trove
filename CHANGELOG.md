# Changelog

All notable changes to Dex Trove are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) — [SemVer](https://semver.org/).

Trove content changes (items learned, updated or excluded) are summarised per release. The authoritative
per-item history is `trove/releases.json` (`dex release list <item>`).

---

## [Unreleased]

---

## [0.3.4] — 2026-11-04

### Added

- **`skill:neo-pragnya/repo-context`:** understand a repository using far fewer tokens. It starts from a small map, then picks Serena,
  repomix, Graphify, `grep` or a plain read, by what measured cheapest for the question. The first wrapper for a new Ananke operation
  (`ananke context`, 0.3.21). Serena is GPL-3.0-or-later and isn't included: the skill says how to run it as its own server.
- The capability matrix now names `ananke context` for context retrieval.
- A roadmap, in `ROADMAP.md`.

---

## [0.3.3] — 2026-11-03

### Security

- **`skill:patched/hf-cloud-sagemaker-iam-preflight` replaces `skill:huggingface/hf-cloud-sagemaker-iam-preflight`.** The
  original's trust check searched the policy for text, so it passed roles SageMaker can't assume: `Deny` statements,
  other actions and lookalike services. If you use it, switch to the fork; `dex release list` shows the deprecation.
- **Known issue in `skill:bmad-method/bmad`:** a version regex in `scripts/setup.py` can hang on a crafted version string,
  for example from an edited lockfile. It isn't fixed here: the other BMAD modules require a skill with that name, and its
  trademark terms ask forks to use a different one.

### Added

- `forks/` and the `patched` source: upstream items with a security fix, recorded as forks with their licence and a
  `CHANGES.md`. The first is the fork above.

---

## [0.3.2] — 2026-11-03

### Added

- **Nine new sources, 739 more items** (1707 in all), checked item by item at the pinned commit. Nearly all are MIT or
  Apache-2.0; 3 are BSD-3-Clause and 1 is CC-BY-4.0:
  BMAD Method (33 skills), Impeccable (1), Spec Kit (9 prompts), Hugging Face (26), Microsoft (180), Scientific skills from
  K-Dense (164), wshobson agents (137), VoltAgent subagents (165) and official Claude Code plugins (24).
- The first items of kind `prompt`: Spec Kit's commands. They install as commands, and expect a project set up with
  `specify init`.
- Licence terms for items declaring BSD-3-Clause or CC-BY-4.0 with no licence file now travel beside the item, as Apache-2.0
  terms already did.
- `withhold:` in `sources.yaml` leaves an item out, with its reason recorded in `EXCLUDED.json`.
- Curated relations for the Spec Kit hand-offs and three same-job pairs across sources.

### Know before using

- **Impeccable** downloads a platform binary from upstream on first use and checks it against the bundled checksums. Set
  `IMPECCABLE_BIN` to use one you installed yourself.
- **BMAD Method** is redistributed under its MIT licence. The BMad names and marks belong to BMad Code, LLC, which doesn't
  endorse Dex Trove.

### Left out

- By licence: 1 official plugin that reserves all rights, and 6 scientific skills (non-commercial, GPL, proprietary or
  undeclared).
- Withheld: 3 skills whose placeholder credentials trip package scanners, and 1 agent that pipes a third-party install
  script into bash.
- Secret-shaped: 13 items.

### Fixed

- A Markdown item named like a licence (`license-engineer.md`) was read as the licence for its whole folder. It wrongly
  excluded 19 VoltAgent agents, which are now admitted.

### Capability matrix

- The six missing capabilities are still missing: no new source covers multi-repository topology, SAS, Jenkins triage,
  Jenkins trigger, Kibana or BPMN. GST and Acuta remain unidentified.

---

## [0.3.1] — 2026-11-03

### Added

- **Capability matrix** (`dex capabilities`, `docs/reference/capability-matrix.md`): for each of the 31 planned
  capabilities, the trove items that serve it, their licences, what's missing, and the next step. It says plainly
  which capabilities have nothing yet. Fit is judged from item descriptions; golden-task evaluation isn't done.
- Named upstream frameworks with verified licences. Impeccable, BMAD and Spec Kit are listed as candidates, not
  ingested. GST and Acuta stay unresolved until someone supplies their repositories.

### Changed

- `similar` relations now name the shared tags or name words.

### Fixed

- The Sources page description omitted four first-party skills. (They were published and listed correctly.)

---

## [0.3.0] — 2026-11-02

Capability memory with releases: every version remembered, exact pins, and a reviewed way for new memory to get in.

### Added

- **Release ledger** (`trove/releases.json`):
  - every version of every item, with digest, files, upstream commit and path, and fork parent;
  - append-only and immutable, except for yank and deprecation markers;
  - `dex learn` appends; `dex validate --since <ref>` fails on any edit or deletion, and CI checks against the
    previous commit;
  - items removed from the trove keep their history.
- **Locks and pinned installs:**
  - `dex lock` pins exact versions and digests in `dex.lock.json`, and `dex verify-lock [--fetch]` checks them;
  - `dex install --locked` installs exactly the pinned versions. A pin that isn't the current release is fetched
    from its upstream Git commit, and nothing is written unless the digest matches.
- **`dex release`:** `list`, `yank`, `unyank`, `deprecate --replaced-by`, `lineage` and `record`. Forks are
  declared with `forked_from:` in `sources.yaml`.
- **Reviewed learning candidates:** `dex candidate check`, `review` and `publish`. A candidate can't publish
  without a passing evaluation (positive and regression cases) and an approving review newer than the evaluation.
  Internal-only candidates can't go to a public source.
- **Typed relations** (`trove/relations.json`, `dex related`):
  - curated `requires`, `complements` and `alternative-to`, with quoted evidence (15 to start);
  - derived plugin membership, forks and replacements;
  - inferred `similar`;
  - dangling references and `requires` cycles fail `dex validate`;
  - item pages group them by type, and none claims compatibility.
- **Install checks** (`dex check-installs`, `trove/install-checks.json`): Dex installs every item into each tool
  layout and checks that the tool can load it. Item pages show the results as **Checked by Dex**, apart from the
  item's self-reported metadata. Dex records no download or usage data.
- **`needs` facet** (taxonomy 1.1.0): what must be installed to run an item (text-only, python, node, shell,
  powershell…), derived from its own files. A plugin needs what its members need. Use it with
  `dex search --needs` or the site rail.
- **`dex overlap`**: groups items of the same kind, task and context that do the same job, and scores each one on
  verifiable signals. Two confirmed overlaps were curated as `alternative-to`.
- **`dex search --rank semantic`**: BM25 with stemming plus taxonomy expansion, for natural questions. It needs no
  model and no network. On 24 labelled questions it reaches recall@10 0.67, against 0.04 for word matching, and
  a test keeps it ahead.
- **`dex ananke handoff`**: turns a Dex lock into exact `[tool.ananke]` pins. It only resolves; nothing runs.
- **Insights page**: recent releases, version counts, install-check failures, overlapping items and relation
  counts, all from repository files.
- **Moderated curation and feedback**: GitHub issue forms for curation proposals and item problems, linked from
  every item page. Identity comes from GitHub, review from maintainers, and the record is permanent. No anonymous
  comments or stars.
- **Site:** kind, source and licence panels update their counts as filters change.
- **Docs:** artifact kinds rewritten in depth, with the whole journey, what happens inside a harness, progressive
  disclosure, how kinds compose, per-kind lifecycle diagrams, the Ananke flow and safety by kind. New Related items
  page. Provenance & versioning covers releases, locks, yank, forks and candidates. New **Capability memory**
  page: memory vs evidence, recipe vs executable plan, how a lesson becomes memory, and why sources are optional.

- **Four new first-party skills** (968 items), each with a standard-library script and curated facets:
  - `idea-developer`: a scoped interview that becomes an approved PRD and an Ananke spec handoff;
  - `tech-selection`: evidence-based technology decision records with licence checks and owned exceptions;
  - `research-questionnaire`: offline HTML questionnaires with explicit download and import, PRD source data and a
    provenance merge;
  - `scaffold-harvesting`: safe, versioned templates from repos you may reuse.
- **Reuse matrix** (`dex docs reuse`, `docs/reference/reuse-matrix.md`): per source, what is reused as-is, enriched,
  forked and excluded, with licence evidence.

### Changed

- When an upstream changes content without bumping its declared version, Dex now assigns the next free patch
  version, so one version never names two contents.

## [0.2.0] — 2026-11-01

### Added

- **Typed facets for every item.** The trove now records task, methodology (SDLC, ADLC, SDD, TDD, BDD…), lifecycle
  phase, role, domain, language, framework, platform and maturity, instead of relying on one loose tag list.
  - The vocabulary is versioned data (`src/dex_trove/taxonomy/ontology.yaml`, taxonomy 1.0.0). Every value has a
    definition and aliases. Validation rejects duplicate ids, ambiguous aliases and merging SDLC with ADLC.
  - `trove/facets.json` is a sidecar: upstream bytes are never edited. Each value records its source (curated,
    upstream metadata, text rules, or derived) and its evidence.
  - 25 items are curated (`curation.yaml`) and marked approved: the first-party skills and the core superpowers and
    Anthropic method skills. Everything else is review-pending.
- **Faceted search.** `dex search` takes `--task`, `--methodology`, `--phase`, `--role`, `--domain`, `--language`,
  `--framework`, `--platform` and `--maturity` (each repeatable), plus `--not facet=value`, `--strict`, `--explain`
  and `--cursor`.
  - Values match OR within a facet and AND across facets. Missing metadata never matches.
  - Counts are disjunctive. An empty result reports which filter to drop, and unknown values are errors.
  - Plain `dex search <words>` output is unchanged.
- **`dex facets list | show | build | doc`**: the taxonomy with counts, one item's facets and evidence, rebuilding the
  sidecar, and generating `docs/reference/taxonomy.md`.
- **Site: "Narrow by what you're doing".** The catalog has facet filters with live disjunctive counts, keyboard
  operation and bookmarkable URLs. Item pages have a **Where it fits** section linking back into the catalog. A
  browser journey checks that the site and `dex search` return the same items.
- **Docs:**
  - [Which artifact when](docs/concepts/which-artifact-when.md): ten pairs people confuse, a decision tree, and
    worked examples from real trove items.
  - [Finding capabilities](docs/guides/finding-capabilities.md): why facets instead of tags, and how filtering works.
  - The generated [taxonomy reference](docs/reference/taxonomy.md).

### Changed

- **Agents installed for Claude Code now launch.** Copilot agents list VS Code tool ids (`codebase`,
  `edit/editFiles`) and models like `GPT-4.1`. Claude Code can't launch a subagent whose tools resolve to nothing.
  - `dex install --target claude` maps tool ids to Claude Code tools, falling back to read-only `Read, Grep, Glob`
    when nothing maps. It keeps or normalises Claude model values and drops the rest.
  - Each change is reported. Only the installed copy changes; the trove and the agent's body stay byte-for-byte.
    Skills were already compatible and are copied as-is.

### Fixed

- **`dex install` no longer deletes your files.** It used to replace any destination with the same name, so a
  skill you wrote yourself in `~/.claude/skills/<name>` could be deleted.
  - It now replaces only copies it installed and you haven't edited (recorded in `.dex-trove-installed.json`), or
    byte-identical copies from an older Dex.
  - Anything else needs `--force`, and a symlink is never followed.

## [0.1.6] — 2026-10-22

### Added

- **First-party skill `package-security-scan`**, so other projects can repeat the work behind 0.1.5. It finds out
  why a package is quarantined by Black Duck-class firewalls and fixes it with free tools:
  - the distribution scan script and a CI job with pinned tools;
  - a gitleaks template for reviewed false positives;
  - a guide that maps firewall report wording to causes and fixes.

  The trove has 964 items.

### Changed

- The gitleaks history scan pins five historical placeholder findings by fingerprint (`.gitleaksignore`), instead
  of allowlisting `trove/` and `tests/` wholesale.

## [0.1.5] — 2026-10-22

### Security

- **The wheel and sdist pass package scanners' secret checks.** Scanners in the Black Duck and JFrog class
  quarantine a wheel that contains credential-shaped strings, even placeholders.
  - The 9 security-teaching items whose placeholders trip those rules are now excluded as `secret-shaped`.
    `EXCLUDED.json` records the rule and line, never the text. The trove has 963 items.
  - `tests/conftest.py` assembles its fake keys at runtime, so the sdist holds none.
- **Licence metadata matches the contents.** `License-Expression` is `MIT AND Apache-2.0 AND OFL-1.1`, not MIT
  alone. A test fails if a newly learned licence isn't declared.

### Added

- `scripts/scan_dist.py` and `make scan` check the built wheel and sdist with free tools:
  - gitleaks and pip-audit block on any finding;
  - GuardDog, Bandit and an inventory of scripts and binaries are reported.
- The `dist-scan` release job runs the scan, and publishing waits for it.

### Fixed

- Items that share a name across kinds (an agent and a skill both called `arch`; 34 such ids) lost their
  `learned_at` and could lose their version history on every learn. The previous record is now looked up by
  kind and id.

## [0.1.4] — 2026-10-21

### Changed

- **Releases publish from CI.** This is the first Dex Trove release built, gated and uploaded by `release-pypi.yml`
  after a tag push, rather than from a laptop.
  - TestPyPI publishing is switched on.
  - Both `pypi` and `testpypi` environments have publish secrets until a trusted publisher replaces them.
  - No trove content changes since 0.1.3.

### Fixed

- **Re-learning an unchanged upstream no longer rewrites `trove.lock.json`.** `learned_at` was restamped on every
  run, so the lock showed churn with nothing changed. The acceptance scenario for this was flaky: it failed only
  when the two runs straddled a clock tick. The timestamp now moves only when the commit, the item counts or the
  exclusions change.

---

## [0.1.3] — 2026-10-21

### Added

- Docs: **switch Dex Trove on with Ananke's `[troves]` setting** (Ananke 0.3.7+): `ananke registry troves enable
  dex-trove` and `sync`. This replaces the roadmap section. An acceptance scenario proves it end to end.

### Changed

- TestPyPI publishing runs only when the `TESTPYPI_ENABLED` repository variable is set. Otherwise the workflow skips
  with setup instructions instead of failing.
- The `ananke` extra locks ananke-plexus 0.3.7.

### Trove

- `neo-pragnya/capability-acceptance` updated: partial-run gate, and browser journeys that use a mock keychain and
  a watchdog.

---

## [0.1.2] — 2026-10-20

### Added

- **Capability acceptance suite** (`acceptance/`): 35 Gherkin scenarios across 12 capabilities.
  - They cover packaging, catalog, install targets and safety, licences, the learn pipeline (two fixture upstreams
    covering every admission path), privacy, notices, Ananke integration and docs export.
  - Real-Chrome **browser journeys** for the website (`acceptance/site/journeys.mjs`) are included.
  - The suite shares Ananke Plexus's harness and its PROMOTE / CONDITIONAL / BLOCK release gate.
- `make acceptance`, `acceptance-wheel`, `acceptance-dist` and `acceptance-site`.
- `acceptance.yml` runs the suite on push and PR. `docs.yml` runs the journeys before deploying, and
  `release-pypi.yml` gates publishing on the wheel.

### Fixed

- Inside a Dex-Trove checkout, an installed `dex` used the wheel's trove (so `dex validate` checked the wrong
  trove). `trove_root()` now prefers the checkout you are working in.

- Duplicates are now caught within a single learn run, not only against a previous run's catalog. The first learn
  on a fresh trove refuses an exact duplicate, and learning twice from unchanged upstreams changes nothing.
- `dex install` exits 1 when nothing was installed (for example a hook without `--allow-exec`), so scripts can't
  mistake a refusal for success. Partial plugin installs still exit 0 and list what was skipped.

### Trove

- 972 items. New first-party skill **`neo-pragnya/capability-acceptance`**: the acceptance harness, scaffolder,
  probe and browser-journeys example behind this release's suite. `living-diagrams` and `interactive-web-motion`
  get new item versions.

---

## [0.1.1] — 2026-10-20

### Added

- **`neo-pragnya/living-diagrams`** (new first-party skill) contains:
  - `plexus.js`, an orbit or web constellation canvas;
  - `diagram-fx.js`, hover effects for any SVG or rendered Mermaid diagram: connected nodes light up, edges flow and
    pulses travel the connections;
  - `term_flow.py`, which builds animated terminal walkthroughs as one CSS-animated SVG from real command output;
  - `cdp_check.mjs`, for verifying animations in real time in headless Chrome.
- Docs site: Mermaid diagrams now respond to hover (`diagram-fx`).

### Changed

- **Text effects:** the random-glyph "scramble" is gone. The site now uses particle text that diffuses away from the
  cursor (hero), a rotating word ("for your agents · copilots · teams · workflows"), and letter hover waves on
  section headings. `data-scramble` remains as an alias for a gentle letter rise.
- **`neo-pragnya/interactive-web-motion`:** adds `data-words`, `data-letters`, `data-particles` and `data-rise`.
  Easing is clamped, which fixes rare frames where shapes exploded into huge wedges.
- **`neo-pragnya/astro-docs-site`:**
  - Mermaid is detected at build time (`remark-mermaid`), so code samples that merely contain a Mermaid fence stay
    code.
  - Shiki syntax highlighting survives sanitising, with light and dark themes and a strict inline-style allow-list.
  - The renderer is lazy, themed from CSS tokens, re-renders on theme toggle, can expand to full screen and shows the
    source when a diagram fails.
  - The scaffolder un-ignores `website/src/lib/` when a Python `.gitignore` hides it.

### Fixed

- Code blocks on the docs site had lost syntax highlighting (the sanitiser stripped Shiki's classes and styles).
- Item pages could try to render Mermaid examples inside Markdown code samples, showing errors.
- `release-testpypi.yml` passed `--trusted-publishing if-necessary`, which uv rejects; it now passes `automatic`.

### Trove

- 971 items (one new first-party skill). `astro-docs-site` and `interactive-web-motion` get new item versions.

---

## [0.1.0] — 2026-10-20

First public release.

### Added

- **`dex` CLI**: `sources`, `learn`, `validate`, `list`, `search`, `show`, `install`, `license`, `notices`, `catalog`,
  `ananke sync`, `docs export`.
- **Learn pipeline**: adapters for the Agent Skills layout (`agent-skills`), `github/awesome-copilot`
  (`awesome-copilot`) and frontmatter Markdown agents (`md-agents`). Each item is fetched at a pinned commit and
  goes through licence resolution, guards and normalisation. Items get their own SemVer, bumped only when their
  content hash changes.
- **Licence policy**: per-item licence classification from the licence *text* (MIT, Apache-2.0, BSD, ISC, 0BSD,
  Unlicense, CC0, CC-BY-4.0, Zlib, BSL-1.0, OFL-1.1 allowed). Restrictive terms (deny markers) win over allow
  fingerprints. Nested licence files are checked; the canonical Apache-2.0 text is shipped when upstream only
  declares it.
- **Guards**: size limits, symlink/junk filtering, real-credential detection, executable-content tagging,
  cross-source duplicate detection, and mirroring of Ananke's secret rules as `secret_flags`.
- **Ananke integration**: every item ships an `ananke.yaml` inside the wheel (≤ 4 path parts, the depth Ananke's
  Python importer scans), so `ananke registry learn python:dex-trove` works with no glue. Plugins become Ananke
  bundles with resolvable members. `dex ananke sync` gives a filtered path.
- **Installers** for Claude Code (`~/.claude` or `./.claude`), GitHub Copilot (`./.github`) and plain directories.
  Plugins expand to their members; hooks require `--allow-exec`.
- **Private items stay private**: `.dexignore` in a source's own folder, or the user-level
  `~/.config/dex-trove/ignore` (`[source:]pattern`), skips items silently. They are never copied, never listed in
  `EXCLUDED.json` or the lock, and never named in this repo.
- **Docs site** (Astro, pastel and interactive): morphing kind glyphs, a cursor-reactive shape field, reveals and
  count-ups via the first-party `interactive-web-motion` motion kit; light by default with a dark toggle.
  Pages: home, searchable catalog, one page per item (install commands, provenance, licence
  evidence, upstream metadata, files, related items), Sources & inspirations, Excluded, and the full
  documentation set.
- **Release engineering mirroring Ananke Plexus**: `uv.lock`, Makefile, mypy strict, pre-commit, CI matrix
  3.11–3.14, a TestPyPI/PyPI build-once pipeline (Trivy gate, provenance attestation, OIDC trusted publishing),
  security, CodeQL, Scorecard, workflow-lint and dependency-review workflows, and a weekly learn PR.

### Trove

- 970 items from four sources: `awesome-copilot` 937 (435 skills, 222 agents, 192 instructions, 72 plugins,
  8 hooks, 8 workflows), `superpowers` 15, `anthropic` 14, `neo-pragnya` 4 (first-party:
  `astro-docs-site`, `interactive-web-motion`, `life-ikigai-architect`, `marvellous-aws-architecture-docs`).
- 37 excluded. Anthropic's `docx`, `pdf`, `pptx` and `xlsx` have proprietary terms; Anthropic's
  `doc-coauthoring` has no licence; 32 awesome-copilot plugins contain only canvas extensions, which are out of
  scope.
- AWS Architecture Icons withheld from `neo-pragnya/marvellous-aws-architecture-docs` (fetched on demand by the
  skill).
