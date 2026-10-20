#!/usr/bin/env python3
"""Build a Life Ikigai Architecture deck from a spec.

    python build_deck.py life.json --out life_ikigai.html
    python build_deck.py life.json --check          # validate only
    python build_deck.py --list-types               # slide types and their fields

The spec is JSON (or a .py file defining SPEC). Images referenced by `image` slides are resolved
relative to the spec file and embedded, so the output is one self-contained HTML file.
"""
import argparse
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ikigai_deck import TYPE_DOCS, build_html, load_spec, validate  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?")
    ap.add_argument("--out", help="output .html (default: <spec>.html next to the spec)")
    ap.add_argument("--check", action="store_true", help="validate only")
    ap.add_argument("--list-types", action="store_true")
    a = ap.parse_args()
    if a.list_types:
        for k, v in TYPE_DOCS.items():
            print(f"{k:10s} {v}")
        return
    if not a.spec:
        ap.error("spec is required")
    sp = pathlib.Path(a.spec)
    spec = load_spec(sp)
    errs = validate(spec)
    if errs:
        print("Spec problems:", *errs, sep="\n  - ")
        sys.exit(1)
    types = Counter(s["type"] for s in spec["slides"])
    print(f"OK: {len(spec['slides'])} slides, {len(spec.get('chapters', []))} chapters · " +
          ", ".join(f"{k}×{v}" for k, v in types.most_common()))
    if a.check:
        return
    out = pathlib.Path(a.out) if a.out else sp.with_suffix(".html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_html(spec, sp.parent), encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
