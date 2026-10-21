# Changelog

All notable changes to Dex Trove are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) — [SemVer](https://semver.org/).

Trove content changes (items learned, updated or excluded) are summarised per release. The authoritative
per-item history is the git history of `trove/` and each item's `version` in `dex.json`.

---

## [Unreleased]

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
