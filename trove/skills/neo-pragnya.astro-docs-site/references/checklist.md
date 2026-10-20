# Launch checklist

## Content

- [ ] `docs/index.md` explains what the project is in the first paragraph
- [ ] Getting started works copy-paste from a clean machine
- [ ] Every page has one `# H1` (or `title:` frontmatter) and a `description:` if it should have a good meta
- [ ] Stats on the landing page are counted from the repo, not estimated
- [ ] Links between docs are relative `.md` links (they work on GitHub *and* the site)

## Build

- [ ] `npm run build` → `astro check` 0 errors, 0 warnings
- [ ] `python scripts/check_site.py dist` → 0 broken links, 0 missing anchors
- [ ] After plugin changes: `rm -rf .astro node_modules/.astro` before building

## Look

- [ ] Home at 1400 px, `?motion=static`: headline on two lines, no text over shapes
- [ ] A doc page with a Mermaid diagram and a callout
- [ ] Dark toggle: readable everywhere, Mermaid switches theme after reload
- [ ] Phone (390 px) via iframes, since headless Chrome can't size a window that small:
  ```html
  <body style="margin:0;display:flex;gap:10px">
    <iframe src="/" style="width:390px;height:1400px;border:0"></iframe>
    <iframe src="/docs/" style="width:390px;height:1400px;border:0"></iframe>
  </body>
  ```
  No horizontal page scroll; code and tables scroll inside themselves.

## Accessibility

- [ ] Keyboard: skip link, focus visible, sidebar reachable
- [ ] Text contrast ≥ 4.5:1 (use the `*-ink` colours for text on pastel fills)
- [ ] Decorative SVG/canvas are `aria-hidden`
- [ ] Reduced motion: `?motion=static` shows the final state of everything

## Deploy

- [ ] `website/.gitignore` excludes `node_modules/`, `dist/`, `.astro/`; `package-lock.json` is committed
- [ ] `.github/workflows/docs-site.yml` sets `SITE_BASE=/<repo>/`
- [ ] Settings → Pages → Source: **GitHub Actions**; only one workflow deploys Pages
- [ ] After the first deploy, open the live URL and run the screenshots again against it
