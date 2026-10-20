#!/usr/bin/env python3
"""Copy motion-kit.js/.css into a site.

    python install_motion_kit.py <site-dir>            # Astro / Vite: <site-dir>/public/motion-kit/
    python install_motion_kit.py <dir> --plain         # any folder: <dir>/motion-kit/
    python install_motion_kit.py <dir> --dest assets/js # explicit destination (relative to <dir>)

Prints the <link>/<script> tags to add to the base layout. Re-running updates the files in place.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
FILES = ("motion-kit.js", "motion-kit.css")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("site", type=Path)
    ap.add_argument("--plain", action="store_true", help="not an Astro/Vite site: copy into <site>/motion-kit/")
    ap.add_argument("--dest", help="destination folder relative to <site>")
    args = ap.parse_args()
    site = args.site.resolve()
    if not site.is_dir():
        print(f"no such directory: {site}", file=sys.stderr)
        return 2
    if args.dest:
        dest = site / args.dest
    elif args.plain or not (site / "astro.config.mjs").exists() and not (site / "package.json").exists():
        dest = site / "motion-kit"
    else:
        dest = site / "public" / "motion-kit"
    dest.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copyfile(ASSETS / name, dest / name)
        print(f"copied {name} → {dest / name}")
    public = site / "public"
    url = "/" + (dest.relative_to(public).as_posix() if dest.is_relative_to(public) else dest.relative_to(site).as_posix())
    print("\nAdd to your base layout (prefix with import.meta.env.BASE_URL in Astro project sites):")
    print(f'  <link rel="stylesheet" href="{url}/motion-kit.css" />')
    print(f'  <script src="{url}/motion-kit.js" defer></script>')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
