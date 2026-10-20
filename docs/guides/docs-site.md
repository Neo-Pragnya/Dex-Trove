---
title: Docs site
description: How the Astro documentation site is generated, built, previewed and deployed.
---

# Docs site

The site at <https://neo-pragnya.github.io/Dex-Trove/> is an [Astro](https://astro.build) static site in
`website/`, the same stack as VICHARA. It has:

| Route | Content |
| --- | --- |
| `/` | overview, counts, quickstarts |
| `/catalog/` | every item, searchable, filterable by kind, source and licence (URL-shareable filters) |
| `/<kind>/<ns.name>/` | one page per item: install commands, source & inspiration, licence evidence, upstream metadata, hook events, files with pinned links, plugin membership, related items, rendered upstream docs |
| `/sources/` | learned sources, mapped sources, evaluated candidates |
| `/excluded/` | every refused candidate with reason and evidence |
| `/docs/…` | this documentation, loaded from `docs/` |

## Build locally

```bash
make docs-build                   # dex docs export + npm run build (astro check && astro build)
# or step by step:
uv run dex docs export --out website/src
cd website && npm ci && npm run dev     # http://localhost:4321
```

## How content gets in

- **Items**: `dex docs export` writes `website/src/content/items/<kind>--<ns>.<name>.md`. The frontmatter is the
  catalog record plus upstream metadata, hook events, file sizes and links, `related` and `part_of`; the body is
  the upstream entry file. The leading H1 is dropped, and relative links and images are rewritten to the upstream
  repo pinned to the learned commit. Generated files are gitignored.
- **Indexes**: `website/src/data/search.json` (compact records for the catalog) and `trove.json` (sources,
  candidates, exclusions, counts).
- **Docs**: the `docs` collection reads `../docs/**/*.md` directly. Links between docs (`../guides/x.md`) are
  rewritten to site routes by a small remark plugin.

## Safety

Upstream Markdown is rendered through `rehype-sanitize`. Never add `set:html` on upstream content.

## Deploy

`.github/workflows/docs.yml` builds with `SITE_BASE=/Dex-Trove/` and deploys to GitHub Pages on every push to
`main`. To enable it: repository **Settings → Pages → Source: GitHub Actions**.

## Adding a page

- A new doc: add a Markdown file under `docs/` with `title` and `description` frontmatter, and link it from
  `docs/index.md`. The sidebar order is defined in `website/src/lib/site.ts` (`DOC_NAV`).
- A new item field: add it in `src/dex_trove/docs_export.py`, then to the schema in
  `website/src/content.config.ts`, then render it in `website/src/pages/[kind]/[slug].astro`.
