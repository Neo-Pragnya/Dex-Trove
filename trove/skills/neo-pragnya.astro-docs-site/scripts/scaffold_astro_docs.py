#!/usr/bin/env python3
"""Scaffold a pastel, interactive Astro documentation site for a repository.

    python scaffold_astro_docs.py <repo> --name "Ananke Plexus" --tagline "Governed agentic engineering"

What it writes (into <repo>/website unless --out):
  * the Astro project from ../templates/website (pastel theme, docs collection reading <repo>/<docs-dir>, sidebar,
    TOC, prev/next, edit links, Mermaid, callouts, .md-link rewriting, sanitised Markdown, 404, favicon)
  * src/lib/site.ts generated from your repo: navigation from mkdocs.yml `nav:` if present, else from the docs tree
  * public/motion-kit/ from the sibling interactive-web-motion skill (morphing glyphs, hero field, reveals)
  * .github/workflows/docs-site.yml (GitHub Pages) with --workflow

Re-running refuses to overwrite an existing site unless --force; --only-site-ts regenerates just site.ts.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE.parent / "templates"
MOTION_KIT = HERE.parent.parent / "interactive-web-motion" / "assets"
TINTS = ["coral", "teal", "lilac", "lemon", "sky", "lime", "pink"]
SHAPES = ["blob>star", "circle>flower", "squircle>spark", "hex>flower8", "triangle>circle", "diamond>star6", "octagon>gear"]


# ---------------------------------------------------------------------------- helpers
def git_remote(repo: Path) -> str | None:
    try:
        url = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    url = re.sub(r"^git@github\.com:", "https://github.com/", url)
    return re.sub(r"\.git$", "", url)


def first_h1(md: Path) -> str | None:
    try:
        text = md.read_text(encoding="utf-8")
    except OSError:
        return None
    fm = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if fm:
        m = re.search(r"^title:\s*['\"]?(.+?)['\"]?\s*$", fm.group(1), re.M)
        if m:
            return m.group(1)
    m = re.search(r"^#\s+(.+?)\s*$", text, re.M)
    return m.group(1) if m else None


def _ignore_tags_loader() -> Any:
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_multi_constructor("", lambda loader, suffix, node: None)  # mkdocs uses !!python/name tags
    return Loader


def nav_from_mkdocs(mkdocs: Path) -> tuple[list[dict[str, Any]], dict[str, str]] | None:
    try:
        import yaml
    except ImportError:
        print("PyYAML not installed; falling back to the docs tree for navigation", file=sys.stderr)
        return None
    data = yaml.load(mkdocs.read_text(encoding="utf-8"), Loader=_ignore_tags_loader())  # noqa: S506
    nav = (data or {}).get("nav")
    if not nav:
        return None
    sections: list[dict[str, Any]] = []
    titles: dict[str, str] = {}
    loose: list[str] = []

    def doc_id(path: str) -> str:
        return re.sub(r"\.md$", "", path).replace("\\", "/")

    def flatten(entries: list[Any]) -> list[str]:
        out = []
        for e in entries:
            if isinstance(e, str):
                out.append(doc_id(e))
            elif isinstance(e, dict):
                for title, target in e.items():
                    if isinstance(target, str) and target.endswith(".md"):
                        titles[doc_id(target)] = str(title)
                        out.append(doc_id(target))
                    elif isinstance(target, list):
                        out.extend(flatten(target))
        return out

    for entry in nav:
        if isinstance(entry, dict):
            for title, target in entry.items():
                if isinstance(target, list):
                    sections.append({"section": str(title), "items": flatten(target)})
                elif isinstance(target, str) and target.endswith(".md"):
                    titles[doc_id(target)] = str(title)
                    loose.append(doc_id(target))
        elif isinstance(entry, str):
            loose.append(doc_id(entry))
    if loose:
        sections.insert(0, {"section": "Overview", "items": loose})
    return sections, titles


def nav_from_tree(docs: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    titles: dict[str, str] = {}
    top = sorted(p for p in docs.glob("*.md"))
    sections: list[dict[str, Any]] = []
    rel = lambda p: p.relative_to(docs).with_suffix("").as_posix()  # noqa: E731
    order = lambda p: (p.stem.lower() not in {"index", "readme"}, p.name.lower())  # noqa: E731
    if top:
        sections.append({"section": "Overview", "items": [rel(p) for p in sorted(top, key=order)]})
    for d in sorted(p for p in docs.iterdir() if p.is_dir() and not p.name.startswith((".", "_", "assets"))):
        files = sorted(d.rglob("*.md"), key=order)
        if files:
            sections.append({"section": d.name.replace("-", " ").replace("_", " ").title(), "items": [rel(p) for p in files]})
    for s in sections:
        for i in s["items"]:
            t = first_h1(docs / f"{i}.md")
            if t:
                titles[i] = t
    return sections, titles


def ts(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)


def site_ts(args: argparse.Namespace, sections: list[dict[str, Any]], titles: dict[str, str], docs: Path) -> str:
    for i, s in enumerate(sections):
        s["shapes"] = SHAPES[i % len(SHAPES)]
        s["tint"] = TINTS[i % len(TINTS)]
    features = []
    for s in sections:
        first = next((i for i in s["items"] if (docs / f"{i}.md").is_file()), None)
        if not first:
            continue
        names = [titles.get(i, i.split("/")[-1].replace("-", " ")) for i in s["items"][:3]]
        features.append(
            {
                "title": s["section"],
                "text": " · ".join(names) + (" · …" if len(s["items"]) > 3 else ""),
                "href": "docs/" if first == "index" else f"docs/{first}/",
                "shapes": s["shapes"],
                "tint": s["tint"],
            }
        )
    stats = []
    for i, spec in enumerate(args.stat or []):
        label, _, value = spec.partition("=")
        stats.append({"label": label, "value": value, "tint": TINTS[i % len(TINTS)]})
    nav = [{"label": "Docs", "href": "docs/"}]
    for spec in args.nav or []:
        label, _, href = spec.partition("=")
        nav.append({"label": label, "href": href})
    nav.append({"label": "GitHub ↗", "href": args.repo_url})
    site = {
        "name": args.name,
        "tagline": args.tagline,
        "description": args.description or args.tagline,
        "repo": args.repo_url,
        "docsDir": args.docs_dir,
        "eyebrow": args.eyebrow or args.tagline,
        "headline": args.headline or args.name,
        "highlight": args.highlight or "",
        "lede": args.lede or args.description or args.tagline,
        "install": args.install or "",
        "ctas": [
            {"label": "Get started →", "href": args.start or "docs/"},
            {"label": "GitHub", "href": args.repo_url},
        ],
        "logoShapes": args.logo_shapes,
        "footer": args.footer or f"{args.name} — open source on GitHub.",
        "footerLinks": [{"label": "GitHub ↗", "href": args.repo_url}],
    }
    return f"""// Generated by the astro-docs-site skill (scaffold_astro_docs.py). Safe to edit by hand.
export const site = {ts(site)} as const;

export const NAV: {{ label: string; href: string }}[] = {ts(nav)};

/** Documentation sidebar: section → doc ids (paths under {args.docs_dir}/ without .md). */
export const DOC_NAV: {{ section: string; items: string[]; shapes: string; tint: string }}[] = {ts(sections)};

/** Titles for docs without `title` frontmatter (from mkdocs.yml nav or the first heading). */
export const DOC_TITLES: Record<string, string> = {ts(titles)};

export const FEATURES: {{ title: string; text: string; href: string; shapes: string; tint: string }}[] = {ts(features)};

export const STATS: {{ label: string; value: string; tint: string }}[] = {ts(stats)};

export function docHref(base: string, id: string): string {{
  return id === "index" ? `${{base}}docs/` : `${{base}}docs/${{id}}/`;
}}
"""


WORKFLOW = """name: docs-site

# Builds the Astro site in {out}/ and deploys it to GitHub Pages.
on:
  push:
    branches: ["main"]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: github-pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pages: read
    env:
      SITE_BASE: {base}
    steps:
      - name: Checkout
        uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false

      - name: Set up Node.js
        uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: {out}/package-lock.json

      - name: Build site (astro check + build)
        working-directory: {out}
        run: |
          npm ci
          npm run build

      - name: Configure GitHub Pages
        uses: actions/configure-pages@983d7736d9b0ae728b81ab479565c72886d7745b # v5

      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@56afc609e74202658d3ffba0e8f6dda462b719fa # v3
        with:
          path: {out}/dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{{{ steps.deployment.outputs.page_url }}}}
    permissions:
      pages: write
      id-token: write
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e # v4
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--tagline", required=True)
    ap.add_argument("--description")
    ap.add_argument("--repo-url", help="defaults to `git remote get-url origin`")
    ap.add_argument("--docs-dir", default="docs")
    ap.add_argument("--out", default="website")
    ap.add_argument("--base", help="GitHub Pages base path, default /<repo-name>/")
    ap.add_argument("--eyebrow")
    ap.add_argument("--headline")
    ap.add_argument("--highlight", help="second line of the headline, shown with a gradient")
    ap.add_argument("--lede")
    ap.add_argument("--install", help="install one-liner shown in the hero, e.g. 'pip install foo'")
    ap.add_argument("--start", help="Get started link (default docs/)")
    ap.add_argument("--stat", action="append", help="hero stat 'Label=123' (repeatable)")
    ap.add_argument("--nav", action="append", help="extra header link 'Label=href' (repeatable)")
    ap.add_argument("--logo-shapes", default="blob star flower hex")
    ap.add_argument("--footer")
    ap.add_argument("--workflow", action="store_true", help="write .github/workflows/docs-site.yml")
    ap.add_argument("--force", action="store_true", help="overwrite an existing site")
    ap.add_argument("--only-site-ts", action="store_true", help="regenerate src/lib/site.ts only")
    args = ap.parse_args()

    repo = args.repo.resolve()
    docs = repo / args.docs_dir
    if not docs.is_dir():
        print(f"no docs folder at {docs}", file=sys.stderr)
        return 2
    args.repo_url = args.repo_url or git_remote(repo) or "https://github.com/OWNER/REPO"
    owner_repo = re.match(r"https://github\.com/([^/]+)/([^/]+)", args.repo_url)
    origin = f"https://{owner_repo.group(1).lower()}.github.io" if owner_repo else "https://example.github.io"
    base = args.base or (f"/{owner_repo.group(2)}/" if owner_repo else "/")
    out = repo / args.out

    mk = repo / "mkdocs.yml"
    parsed = nav_from_mkdocs(mk) if mk.is_file() else None
    sections, titles = parsed if parsed else nav_from_tree(docs)
    # Keep titles from headings for docs mkdocs didn't title.
    for s in sections:
        for i in s["items"]:
            if i not in titles and (t := first_h1(docs / f"{i}.md")):
                titles[i] = t

    if args.only_site_ts:
        (out / "src" / "lib" / "site.ts").write_text(site_ts(args, sections, titles, docs), encoding="utf-8")
        print(f"regenerated {out / 'src/lib/site.ts'}")
        return 0
    if out.exists() and any(out.iterdir()) and not args.force:
        print(f"{out} exists — pass --force to overwrite (or --only-site-ts)", file=sys.stderr)
        return 2

    pkg = re.sub(r"[^a-z0-9-]+", "-", args.name.lower()).strip("-")
    for src in (TEMPLATES / "website").rglob("*"):
        if src.is_dir():
            continue
        dest = out / src.relative_to(TEMPLATES / "website")
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8")
        text = (
            text.replace("__PKG_NAME__", pkg)
            .replace("__SITE_ORIGIN__", origin)
            .replace("__DOCS_DIR__", args.docs_dir.strip("/"))
        )
        dest.write_text(text, encoding="utf-8")
    (out / "src" / "lib" / "site.ts").write_text(site_ts(args, sections, titles, docs), encoding="utf-8")
    kit = out / "public" / "motion-kit"
    if MOTION_KIT.is_dir():
        kit.mkdir(parents=True, exist_ok=True)
        for name in ("motion-kit.js", "motion-kit.css"):
            shutil.copyfile(MOTION_KIT / name, kit / name)
    else:
        print("warning: interactive-web-motion skill not found next to this skill; add public/motion-kit/ yourself")
    gi = out / ".gitignore"
    gi.write_text("node_modules/\ndist/\n.astro/\n", encoding="utf-8")
    if args.workflow:
        wf = repo / ".github" / "workflows" / "docs-site.yml"
        wf.parent.mkdir(parents=True, exist_ok=True)
        wf.write_text(WORKFLOW.format(out=args.out, base=base), encoding="utf-8")
        print(f"wrote {wf}")
    n = sum(len(s["items"]) for s in sections)
    print(f"scaffolded {out} — {len(sections)} sections, {n} docs, base {base}")
    print(f"next: cd {out} && npm install && npm run build   (preview: npm run dev)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
