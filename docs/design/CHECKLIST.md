# Dex Trove — Implementation Checklist

Living checklist; update as work lands. Design: [DESIGN.md](DESIGN.md).

Legend: `[x]` done · `[~]` in progress / partial · `[ ]` todo

## Phase 0 — Research & design
- [x] Survey Ananke registry contract (manifest schema, python importer, ≤4-part wheel depth, `ananke://` refs)
- [x] Survey awesome-copilot layout (skills, agents, instructions, hooks, workflows, plugins) and licensing
- [x] Survey first-party skills (`Skills/`), flag AWS icon redistribution
- [x] Verify candidate source licences via GitHub API (2026-10-19)
- [x] Design doc (`DESIGN.md`) and this checklist

## Phase 1 — Package core
- [x] `pyproject.toml` (hatchling, `dex` script, trove force-include into wheel)
- [x] ~~`models.py`~~ — folded into dataclasses in `sources.py` / `adapters.py` / `learn.py` (no pydantic dependency)
- [x] `licenses.py` — SPDX normalise, text fingerprints, deny markers, expression evaluation
- [x] `frontmatter.py` — tolerant YAML frontmatter parsing
- [x] `sources.py` + `sources.yaml` — load, git shallow fetch @ ref, local override, commit pin
- [x] Adapters: `agent-skills`, `awesome-copilot`, `md-agents`
- [x] Guards: size, symlink, junk, secrets, exec tagging, duplicates, name slug/collision
- [x] Normaliser: verbatim copy + `ananke.yaml` + `dex.json` + `LICENSE.upstream` + item SemVer bump
- [x] Catalog, `EXCLUDED.json`, `trove.lock.json`, `THIRD_PARTY_NOTICES.md`
- [x] CLI: `sources learn validate list search show install license ananke notices docs`

## Phase 2 — Learn the initial trove
- [x] Learn first-party `neo-pragnya` (icons excluded)
- [x] Learn `awesome-copilot`
- [x] Learn `anthropic` (expect docx/pdf/pptx/xlsx denied)
- [x] Learn `superpowers`
- [x] Review `EXCLUDED.json` for false positives

## Results so far (2026-10-19)
- Learned 970 items: awesome-copilot 937 (435 skills, 222 agents, 192 instructions, 72 plugins, 8 hooks, 8 workflows),
  superpowers 15, anthropic 14, neo-pragnya 4. 37 excluded: 32 canvas-only plugins (out of scope), anthropic
  docx/pdf/pptx/xlsx (proprietary text), anthropic doc-coauthoring (no licence at all).
- Found during learn and fixed: nested licences (OFL fonts in anthropic/canvas-design → recorded as `components`;
  strict filenames so `pdftk-server-license.md` docs aren't mistaken for terms); Apache declared only in frontmatter
  (7 items) → canonical Apache text shipped as `LICENSE.upstream`; first-party URLs point into Dex-Trove.
- Wheel 15 MB / sdist 11.6 MB; every `ananke.yaml` at wheel depth 4. All 970 manifests pass Ananke's `ArtifactManifest`.
- `ananke registry learn python:dex-trove` (clean venv, installed wheel): 961 registered, 9 refused by Ananke's secret
  scanner — all placeholders in security-teaching content (`"PINECONE_API_KEY"`, `sk_live_…`). Dex now
  mirrors those rules → `secret_flags` + tag `ananke-secret-flag`; `dex ananke sync` skips them unless
  `--include-flagged`. Full sync: 961 registered, exit 0; re-sync is idempotent (skipped); bundles resolve to members.

## Phase 3 — Ananke integration
- [x] `dex ananke sync` via `ananke registry learn`
- [x] Verify with local Ananke venv: register a sample of items, `ananke registry search` finds them
- [x] Verify `ananke registry learn python:dex-trove` against an installed wheel
- [ ] Ananke follow-up: placeholder-aware secret rule or per-artifact allow-list (9 false positives today)
- [ ] Propose Ananke `[dex]` extra + `[troves]` policy setting (separate PR in Ananke-Plexus)

## Phase 4 — Docs site
- [x] `dex docs export` → Astro content + JSON
- [x] Astro site: home, catalog search, per-item page, sources & inspirations, excluded, design
- [x] `astro build` passes locally
- [x] GitHub Pages workflow

## Phase 5 — Quality & release
- [x] pytest suite (licences, adapters, normaliser, CLI, Ananke manifest validity)
- [x] ruff clean
- [x] CI workflow (validate, tests, docs build)
- [x] Release workflow (uv build → PyPI trusted publishing on tag)
- [x] Scheduled learn workflow (opens PR)
- [x] README with quickstart
- [x] Pushed to GitHub `main`; Pages enabled (build from Actions); `pypi`/`testpypi` environments created
- [x] Live site: https://neo-pragnya.github.io/Dex-Trove/ (all six workflows green on 434c062: ci, security, codeql, scorecard, workflow-lint, docs)
- [x] First CI round surfaced and fixed: gitleaks hits on placeholder examples quoted in docs (elided; pushed commit
      allow-listed like Ananke), and `dex ananke sync` not finding `ananke` in an unactivated venv (now looks beside
      the interpreter)
- [ ] First release `v0.1.0` (TestPyPI → PyPI), tag + GitHub Release: *blocked on publish credentials (see below)*
- [ ] **Owner action:** add PyPI/TestPyPI trusted publishers (project `dex-trove`, repo `Neo-Pragnya/Dex-Trove`,
      workflows `release-pypi.yml` / `release-testpypi.yml`, environments `pypi` / `testpypi`) for future tags

## Results — docs & quality (2026-10-19)
- `astro check`: 0 errors / 0 warnings; `astro build`: 975 pages (970 items + home, catalog, sources, excluded, design).
- Verified rendering with headless Chrome at 1280 px and a true 390 px (iframe), in dark mode: no horizontal page scroll.
- Relative upstream image paths broke Astro's asset pipeline (`skills/napkin`): export now pins them to upstream URLs.
- 31 tests pass; ruff check + format clean; `dex validate` → 970 items valid (with Ananke 0.3.4, same as PyPI).
- README commands verified end to end: claude / copilot / dir installs, plugin → members, hooks gated by `--allow-exec`.

## Phase 6 — Ananke-parity release engineering & documentation (2026-10-20)
- [x] Mirror Ananke config: `uv.lock` + `uv sync --all-extras`, Makefile (same targets incl. `publish-*`), `.env.example`,
      `.pre-commit-config.yaml`, `.trivyignore`, `.gitleaks.toml`, CHANGELOG (Keep a Changelog), CONTRIBUTING, SECURITY,
      CODE_OF_CONDUCT
- [x] mypy strict (clean); coverage 85 % (CI floor 80 %); 39 tests
- [x] Workflows mirroring Ananke: ci (3.11–3.14 matrix + wheel smoke test with Ananke + docs build), release-pypi and
      release-testpypi (build once → Trivy → attest → OIDC publish, token fallback, idempotent if already published),
      security (Trivy package gate + non-blocking trove scan, Semgrep, pip-audit, gitleaks), codeql, scorecard,
      workflow-lint, dependency-review, docs (Pages), learn (weekly PR); all actions SHA-pinned
- [x] actionlint clean; zizmor clean (fixed cache-poisoning in release builds and workflow-level `security-events`)
- [x] pip-audit: no known vulnerabilities
- [x] Documentation set (Ananke-style): overview, 6 concepts, 7 guides, 8 references (CLI verified against `--help`,
      Python API examples executed, manifests quoted from the real trove)
- [x] Website: docs section (sidebar, on-page TOC, prev/next, edit links, `.md` links → routes), rich item pages (at a
      glance, upstream metadata, hook events, bundled items, part-of, related, files with sizes + pinned links, install
      matrix), featured first-party skills, theme toggle, copy buttons, 404; 999 pages; 0 broken internal links / anchors
- [x] Re-learned all sources at latest upstream (awesome-copilot `613efc8`, unchanged → 937 items)

## Phase 7 — Privacy, new identity, motion, sibling sites (2026-10-20)
- [x] `.dexignore` (in the source's own folder) + user-level `~/.config/dex-trove/ignore` (`[source:]pattern`):
      ignored items are skipped silently (not copied, not in EXCLUDED.json or the lock); tests added
- [x] Personal first-party skills hidden via `Skills/.dexignore` (names kept out of this repo) and removed from the
      trove; git history rebuilt so no commit contains them
- [x] Identity: "Dex Trove — a trove of dexterities for your agents" (Dexterity Trove) across site, README, package
- [x] Pastel light theme by default (crimson-orange, lemon, chartreuse, turquoise, lilac, sky, pink on warm
      off-white), dark as an opt-in toggle; text colours verified ≥ 5.5:1 contrast
- [x] Graphify-inspired interactions via motion-kit: morphing kind glyphs (each kind = rest → hover shape), a
      cursor-reactive shape field in the hero, scramble headings, blur reveals, count-ups, tilt/spotlight cards,
      marching-ants CTAs, sources marquee; reduced-motion and `?motion=static` respected; lazy glyph init for the
      968-card catalog
- [x] New first-party skills registered (Claude Code symlinks, `.skill` packages, learned into the trove):
      `astro-docs-site` (scaffolder + templates + link checker) and `interactive-web-motion` (motion-kit)
- [x] Ananke Plexus: Astro site scaffolded with the skill (nav imported from mkdocs.yml), Dex Trove guide, Pages
      via docs-site.yml; MkDocs kept only for the offline docs bundled in the wheel; committed on branch
      `feat/astro-docs-site` (not pushed)
- [x] VICHARA: motion-kit layer (hero field around the orbit, morphing orbit centre, lens/doc-card glyphs + tilt,
      reveals, count-up) keeping its green identity; lint/tests/build green; committed on branch
      `feat/interactive-visuals` (not pushed)
- [x] Dex site: 999 pages, 27 701 internal links, 0 broken, 0 missing anchors (`check_site.py`)

## Phase 8 — Living diagrams, real Mermaid, gentler text effects (2026-10-20)
- [x] Mermaid fixed at the root. The sanitiser stripped `language-*`, so the client had to guess diagrams from their
      text. Now `remark-mermaid` marks real fences at build time, and Shiki highlighting is restored behind a strict
      style allow-list (`rehype-class-names` normalises Shiki's `class`). The renderer is lazy, themed from CSS tokens,
      re-renders on theme toggle, can expand and shows the source on failure. Verified on all Mermaid pages of the
      Dex, Ananke and VICHARA sites.
- [x] Scramble retired across the Dex, Ananke and VICHARA sites. Particle text, rotating words and letter hover waves
      (colour, weight and typeface) replace it.
- [x] New first-party skill `living-diagrams` (plexus.js, diagram-fx, term_flow.py, cdp_check.mjs): registered,
      packaged and learned into the trove.
- [x] Ananke: animated flows extracted from its infographics (intent to proof, governed execution, code graph, the
      verifiable pipeline), plus three walkthroughs built from real CLI output, a "See It in Action" guide, a PyPI link
      and a version chip.
- [x] Released 0.1.1 to PyPI.

## Phase 9 — Capability acceptance and release gate (2026-10-20)
- [x] `acceptance/`: Gherkin scenarios drive the real CLI in sandboxes (fresh project or maintainer checkout,
      isolated HOME). The harness is shared with Ananke Plexus (byte-identical copy).
- [x] Capability catalog with blockers, a Week-12-style gate (PROMOTE / CONDITIONAL / BLOCK) with evidence, and
      CLI surface coverage (12/12 commands).
- [x] Learn fixtures cover every admission path: MIT, Apache (frontmatter), proprietary, none, bundled GPL, AWS key,
      6 MB file, duplicate, scripts and `.dexignore`. Secrets and big files are generated at runtime.
- [x] Browser journeys (real headless Chrome via CDP): search/filters, item page, Mermaid render + hover,
      highlighting, theme, 404, 390 px. Run in `docs.yml` before deploy.
- [x] The wheel-mode run found and fixed `trove_root()` preferring the wheel over the working checkout.
- [x] Known issues fixed in 0.1.2: duplicate detection within a single learn run; `install` refusals exit 1.
- [x] New first-party skill `capability-acceptance` (harness + scaffolder + probe + journeys) learned into the trove.

## Follow-ups / backlog
- [ ] Move first-party skills into git (this repo's `first-party/` or their own repo) so CI can re-learn them
- [x] Light-mode visual pass on the docs site (verified by screenshot)
- [ ] Enable `huggingface/skills`, `microsoft/skills`, `K-Dense-AI/claude-scientific-skills`
- [ ] Tune `md-agents` for `wshobson/agents`, `VoltAgent/awesome-claude-code-subagents`
- [ ] `rules` adapter for awesome-cursorrules
- [ ] Decision on CC-BY-SA (trailofbits/skills)
- [ ] Discovery mode: scan link lists (awesome-claude-code, awesome-mcp-servers) for new candidate repos + licences
