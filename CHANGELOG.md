# Changelog

All notable changes to Dex Trove are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) — [SemVer](https://semver.org/).

Trove content changes (items learned, updated or excluded) are summarised per release. The authoritative
per-item history is the git history of `trove/` and each item's `version` in `dex.json`.

---

## [Unreleased]

### Trove

- `neo-pragnya/astro-docs-site` updated. The scaffolder now un-ignores `website/src/lib/` when a Python
  `.gitignore` hides it. The skill adds advice on giving each site its own theme layer, and on testing phone widths
  in an iframe.

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
