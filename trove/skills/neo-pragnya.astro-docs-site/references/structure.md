# Site structure

```text
website/
├── astro.config.mjs            base from SITE_BASE; remark: doc links + callouts; rehype-sanitize (stable ids)
├── package.json                astro 7, @astrojs/markdown-remark, rehype-sanitize, mermaid; check + build scripts
├── public/
│   ├── favicon.svg
│   └── motion-kit/             motion-kit.js + .css (interactive-web-motion skill)
└── src/
    ├── content.config.ts       `docs` collection = glob("../docs/**/*.md"), id = path without .md
    ├── lib/
    │   ├── site.ts             ← everything you customise: site copy, NAV, DOC_NAV, DOC_TITLES, FEATURES, STATS
    │   ├── remark-doc-links.ts relative .md links → /docs/<route>/ (keeps #fragments, honours SITE_BASE)
    │   └── remark-callouts.ts  > [!NOTE] and !!! admonitions → <blockquote class="callout callout-…">
    ├── components/
    │   ├── Layout.astro        header (morphing logo glyph, nav, theme toggle), footer, fonts, copy buttons
    │   ├── Glyph.astro         <svg data-morph> with a tint
    │   └── Mermaid.astro       client-side Mermaid (pastel "base" theme; dark when toggled)
    ├── pages/
    │   ├── index.astro         hero (aurora + field + scramble), stats, features, docs grid
    │   ├── docs/[...slug].astro sidebar / article / TOC / pager / edit link
    │   └── 404.astro
    └── styles/global.css       tokens (palette strong/soft/ink), layout, docs, callouts, dark opt-in
```

## `site.ts`

| Export | Purpose |
| --- | --- |
| `site` | name, tagline, description, repo, docsDir, eyebrow, headline, highlight, lede, install, ctas, logoShapes, footer, footerLinks |
| `NAV` | header links (`href` relative to the base, or absolute) |
| `DOC_NAV` | `[{section, items: [docId…], shapes: "rest>hover", tint}]`: sidebar order. Docs not listed appear under "More" |
| `DOC_TITLES` | `{docId: "Title"}` for pages without `title` frontmatter |
| `FEATURES` | landing cards `{title, text, href, shapes, tint}` |
| `STATS` | `{label, value, tint}`: count-up numbers (must be true) |

Tints: `coral lemon lime teal lilac sky pink`. Shapes: see the interactive-web-motion skill.

## Adding a custom page

Create `src/pages/<name>.astro`, wrap in `<Layout title="…">`, use `.card`, `.chip`, `.grid-cards`, `Glyph`,
`data-reveal`, and add a `NAV` entry.

## Adding a generated collection

For data-driven pages (catalogs, API references), write Markdown or JSON into `src/content/<name>/` from a build
script (gitignore it), add a collection in `content.config.ts`, and a `[slug].astro` route. Dex Trove's item pages
are an example: `dex docs export` writes ~1 000 Markdown files before `astro build`.
