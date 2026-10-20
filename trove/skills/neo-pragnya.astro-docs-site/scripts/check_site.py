#!/usr/bin/env python3
"""Check a built static site (e.g. website/dist): broken internal links, missing in-page anchors, empty pages.

    python check_site.py website/dist [--base /Repo/]

Exit 1 if anything is broken. External links are not fetched.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse

HREF = re.compile(r'href="([^"]+)"')
ID = re.compile(r'\sid="([^"]+)"')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dist", type=Path)
    ap.add_argument("--base", default="/", help="site base path the site was built with (SITE_BASE)")
    args = ap.parse_args()
    dist = args.dist.resolve()
    base = "/" + args.base.strip("/") + "/" if args.base.strip("/") else "/"
    pages = sorted(dist.rglob("*.html"))
    ids: dict[Path, set[str]] = {}
    broken: Counter[str] = Counter()
    anchors: Counter[str] = Counter()
    checked = 0

    def ids_of(path: Path) -> set[str]:
        if path not in ids:
            ids[path] = set(ID.findall(path.read_text(errors="ignore")))
        return ids[path]

    for page in pages:
        html = page.read_text(errors="ignore")
        for href in HREF.findall(html):
            if href.startswith(("http:", "https:", "mailto:", "data:", "//")):
                continue
            checked += 1
            u = urlparse(href)
            if href.startswith("#"):
                target = page
            else:
                path = unquote(u.path)
                if not path.startswith("/"):
                    path = "/" + str((page.parent.relative_to(dist) / path).as_posix())
                if not path.startswith(base):
                    broken[f"{href} (outside base {base})"] += 1
                    continue
                rel = path[len(base):]
                target = dist / rel / "index.html" if (not rel or rel.endswith("/")) else dist / rel
                if not target.exists() and (dist / rel).is_dir():
                    target = dist / rel / "index.html"
                if not target.exists():
                    broken[f"{href}  ← {page.relative_to(dist)}"] += 1
                    continue
            if u.fragment and target.suffix == ".html" and unquote(u.fragment) not in ids_of(target):
                anchors[f"{href}  ← {page.relative_to(dist)}"] += 1
    print(f"pages: {len(pages)}  internal links checked: {checked}")
    print(f"broken links: {sum(broken.values())}")
    for k, v in broken.most_common(20):
        print(f"  {v}× {k}")
    print(f"missing anchors: {sum(anchors.values())}")
    for k, v in anchors.most_common(20):
        print(f"  {v}× {k}")
    return 1 if broken or anchors else 0


if __name__ == "__main__":
    raise SystemExit(main())
