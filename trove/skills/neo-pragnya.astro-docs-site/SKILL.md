---
name: astro-docs-site
description: "Set up (or migrate to) a modern Astro documentation website for a repository, deployed to GitHub Pages: docs read straight from the repo's docs/ folder (one source of truth for GitHub and the site), sidebar + on-page TOC + prev/next + edit-on-GitHub, Mermaid diagrams, GitHub alerts and MkDocs admonitions, .md links rewritten to routes, sanitised Markdown, a pastel interactive landing page (morphing SVG glyphs, cursor-reactive shape field, reveals, count-up stats), light/dark toggle, 404, link checker, Pages workflow and screenshot verification. Use whenever someone wants docs for a repo, a GitHub Pages site, a project website or landing page, to move off MkDocs/Docusaurus/Jekyll, to 'make the docs look modern', or to give a new repo 'all the elements' of a docs setup, even if they don't say Astro."
---

# Astro Docs Site

Scaffold a complete, good-looking documentation site for any repository in minutes, then tailor it. The result is
an Astro static site in `website/` that reads Markdown **directly from the repo's `docs/` folder**: the same files
render on GitHub and on the site, so there is nothing to sync.

Proven on: Dex Trove (≈1 000 pages, catalog + docs), Ananke Plexus (migrated from MkDocs, nav and titles imported
from `mkdocs.yml`), VICHARA.

## What you get

| Element | Details |
| --- | --- |
| Landing page | pastel gradient hero with a cursor-reactive shape field, headline + gradient highlight, CTAs (magnetic, marching ants), install one-liner, count-up stats, feature cards with morphing glyphs, a "browse the docs" grid |
| Docs pages | `/docs/<path>/` for every `docs/**/*.md`; sidebar grouped by section (each with its own glyph and tint), on-page TOC, prev/next, "Edit this page on GitHub" |
| Markdown | Mermaid (pastel theme, dark-aware), GitHub alerts `> [!NOTE]` and MkDocs `!!! warning "Title"` → callouts, relative `.md` links → site routes, relative images via Astro assets, `rehype-sanitize` with stable heading ids |
| Theme | light pastel by default (crimson-orange, lemon, chartreuse, turquoise, lilac, sky, pink on warm off-white), opt-in dark toggle, Inter / Space Grotesk / JetBrains Mono |
| Motion | `public/motion-kit/` from the **interactive-web-motion** skill: morphing glyphs, field, scramble, reveals, count-up, tilt, ants; honours reduced motion |
| Delivery | `.github/workflows/docs-site.yml` (SHA-pinned actions, Pages deploy with `SITE_BASE`), `npm run build` = `astro check` + `astro build` |
| Quality | `scripts/check_site.py` (broken links + missing anchors), headless-Chrome screenshot recipe, 404 page |

## Workflow

1. **Inventory the repo.** Is there a `docs/` folder? An `mkdocs.yml` with a `nav:` (the scaffolder imports it)?
   README-only? If docs don't exist yet, create `docs/index.md` and a few pages first. A docs site with no docs is
   just a landing page.
2. **Scaffold:**
   ```bash
   python scripts/scaffold_astro_docs.py <repo> \
     --name "Project" --tagline "One-line promise" \
     --headline "Short, bold claim" --highlight "the twist." \
     --lede "Two sentences: what it is and why it matters." \
     --install "pip install project" --start "docs/guides/getting-started/" \
     --stat "Docs pages=23" --stat "Integrations=6" \
     --nav "Related ↗=https://…" --workflow
   ```
   - `--repo-url` defaults to the git remote. The Pages base defaults to `/<repo>/`.
   - Navigation comes from `mkdocs.yml` `nav:` if present, otherwise from the folder tree (top-level `*.md` →
     Overview, then one section per sub-folder).
   - **Stats must be true.** Count them from the repo (files, classes, adapters), never invent them.
3. **Build and check:**
   ```bash
   cd <repo>/website && npm install && npm run build
   python <skill>/scripts/check_site.py dist        # 0 broken links, 0 missing anchors
   ```
4. **Look at it** (see Verify) and tailor `src/lib/site.ts` (copy, features, stats, nav) and `src/pages/index.astro`.
   Re-run with `--only-site-ts` to regenerate navigation after adding docs.
5. **Wire up deploy:** commit `website/` (not `node_modules/`, `dist/`, `.astro/`) and the workflow, then in the repo
   settings set **Pages → Source: GitHub Actions**. If an older Pages workflow exists (e.g. MkDocs), replace or
   disable it so only one deploys.

## Migrating from MkDocs

- Keep `docs/` as is. Astro reads the same files. If the project also *packages* MkDocs for offline use (e.g. a
  `docs build` CLI command), keep `mkdocs.yml` for that and only move the hosted site.
- Supported out of the box: Mermaid fences, `!!! type "Title"` admonitions (lazy-continuation body),
  `> [!NOTE]` alerts, relative links and images, tables, footnotes.
- Not supported (rewrite them if you find any): content tabs `=== "Tab"`, `--8<--` snippets, `{ .class }`
  attribute lists, `markdown="1"` HTML blocks. Find them with
  `grep -rnE '^=== |--8<--|\{ ?[:#.][a-z]|markdown="1"' docs`.

## Gotchas (learned the hard way)

- **Astro caches rendered Markdown** in `.astro/` and `node_modules/.astro/`, keyed by file content. After
  changing a remark/rehype plugin, run `rm -rf .astro node_modules/.astro`, or the old HTML is served.
- **Smart quotes run before your plugins see some text.** Match `["“”]` in any pattern that reads quoted titles.
- `rehype-sanitize` prefixes ids with `user-content-` by default, which breaks TOC anchors. The template sets
  `clobberPrefix: ""`.
- Never put the shape field under body text: the template masks it to the right side (and the bottom on phones).
- `astro check` needs `@types/node` and `@types/mdast` for the remark plugins (already in the template).
- Headless screenshots catch animations mid-flight. Use `?motion=static` for the settled state.

## Verify

```bash
cd website/dist && python3 -m http.server 4321 &
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$C" --headless=new --hide-scrollbars --virtual-time-budget=5000 --window-size=1400,1800 \
  --screenshot=home.png "http://localhost:4321/?motion=static"
"$C" --headless=new --hide-scrollbars --virtual-time-budget=6000 --window-size=1400,1200 \
  --screenshot=doc.png "http://localhost:4321/docs/<a-page-with-mermaid>/"
```

Check: hero copy readable, no text over shapes, sidebar active state, TOC, a Mermaid diagram, a callout, the dark
toggle, and a 390 px phone view (iframe trick in `references/checklist.md`).

## Files

| Path | What |
| --- | --- |
| `scripts/scaffold_astro_docs.py` | generate `website/` + `site.ts` + workflow |
| `scripts/check_site.py` | broken links / anchors in a built site |
| `templates/website/` | the Astro project (tokens `__PKG_NAME__`, `__SITE_ORIGIN__`, `__DOCS_DIR__`) |
| `references/structure.md` | how the site is put together and where to customise |
| `references/checklist.md` | launch checklist (content, a11y, SEO, deploy) |
