"""Build architecture docs from a spec file - Marvellous AWS Architectures Docs.

    python scripts/build_arch.py path/to/arch_specs.py --out docs/architecture [--title "My system"] [--intro "..."]
           [--only wwi-arch wwi-deploy] [--no-stages] [--no-html]

The spec file defines `SPECS = [Spec, ...]` (or `ALL = [...]`). For every spec it writes
  svg/<id>.svg                  complete system, numbered flows light up in turn (CSS - animates even as <img>)
  svg/<id>-stage-NN.svg         "map so far" per Stage (new = pink glow, built = solid, future = faded, deleted = crossed)
  drawio/<id>.drawio            editable diagram with draw.io's native AWS shapes
and one shareable, self-contained docs page:
  index.html                    every spec as an interactive widget (▶ play the flow, step, jump from the legend,
                                build it up stage by stage), a numbered step table, and download links

Checks (the build fails on them): every flow endpoint exists, flow numbers are 1..N in order, ids are unique.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import archlib  # noqa: E402


def load_specs(path: Path) -> list:
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    specs = getattr(mod, "SPECS", None) or getattr(mod, "ALL", None)
    if not specs:
        raise SystemExit(f"{path}: define SPECS = [Spec, ...]")
    return specs


def validate(spec) -> None:
    ids = [n.id for n in spec.nodes]
    dup = {i for i in ids if ids.count(i) > 1}
    assert not dup, f"{spec.id}: duplicate node ids {sorted(dup)}"
    bad = [f.n for f in spec.flows if f.src not in ids or f.dst not in ids]
    assert not bad, f"{spec.id}: flows with unknown nodes {bad}"
    nums = [f.n for f in spec.flows]
    assert nums == list(range(1, len(nums) + 1)), f"{spec.id}: flow numbers must be 1..N in order, got {nums}"
    stages = {s.k for s in spec.stages}
    if stages:
        used = {n.stage for n in spec.nodes} | {f.stage for f in spec.flows}
        missing = sorted(used - stages)
        assert not missing, f"{spec.id}: stage numbers used but not declared in stages: {missing}"


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#F5F6F7;--panel:#fff;--ink:#16191F;--muted:#5F6B7A;--line:#D5DBDB;--accent:#FF9900;--shadow:0 6px 24px rgba(22,25,31,.08)}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0F141A;--panel:#161D26;--ink:#E9EDF1;--muted:#9AA6B2;--line:#2A3441;--shadow:none}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 "Amazon Ember",Inter,system-ui,-apple-system,Segoe UI,sans-serif}}
header{{background:#232F3E;color:#fff;padding:28px max(16px,5vw) 22px}}header h1{{margin:0 0 6px;font-size:clamp(24px,3.4vw,36px)}}
header p{{margin:0;max-width:960px;color:#D5DBDB}}header .tag{{display:inline-block;margin-bottom:10px;font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#FF9900}}
nav{{position:sticky;top:0;z-index:5;background:var(--panel);border-bottom:1px solid var(--line);padding:8px max(16px,5vw);display:flex;gap:8px;flex-wrap:wrap}}
nav a{{color:var(--ink);text-decoration:none;font-size:14px;padding:4px 10px;border-radius:99px;border:1px solid var(--line)}}nav a:hover{{border-color:#FF9900}}
main{{padding:12px max(16px,5vw) 60px;max-width:1700px;margin:0 auto}}
section{{margin:34px 0}}h2{{font-size:clamp(20px,2.4vw,28px);border-left:6px solid #FF9900;padding-left:12px;margin:0 0 6px}}
.sub{{color:var(--muted);margin:0 0 12px}}.dl{{font-size:14px;color:var(--muted)}}.dl a{{color:#0972D3}}
table{{border-collapse:collapse;width:100%;background:var(--panel);border-radius:10px;overflow:hidden;box-shadow:var(--shadow);font-size:14px;margin-top:12px}}
th,td{{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{background:rgba(255,153,0,.12);font-size:12px;text-transform:uppercase;letter-spacing:.05em}}
td.n b{{display:inline-grid;place-items:center;width:24px;height:24px;border-radius:50%;background:#232F3E;color:#fff;font-size:12px}}
details{{margin-top:10px}}summary{{cursor:pointer;color:var(--muted)}}
footer{{color:var(--muted);font-size:13px;padding:20px max(16px,5vw);border-top:1px solid var(--line)}}
{archviz_css}
</style></head><body>
<header><div class="tag">Architecture docs</div><h1>{title}</h1><p>{intro}</p></header>
<nav>{nav}</nav>
<main>{sections}</main>
<footer>Generated with <b>Marvellous AWS Architectures Docs</b> (architecture as code). AWS service icons: official AWS Architecture Icons.
Every diagram is also available as an animated SVG and an editable draw.io file.</footer>
<script>{archviz_js}</script>
</body></html>"""


def section(spec, uid: str) -> str:
    stages_note = ""
    if spec.stages:
        rows = "".join(f"<tr><td><b>{html.escape(s.parts)}</b></td><td>{html.escape(s.title)}</td><td>{html.escape(s.blurb)}</td>"
                       f"<td><a href='svg/{spec.id}-stage-{s.k:02d}.svg'>map</a></td></tr>" for s in spec.stages)
        stages_note = (f"<details><summary>Build stages ({len(spec.stages)}) - the system as it grows</summary>"
                       f"<table><tr><th>Stage</th><th>Title</th><th>What appears</th><th>SVG</th></tr>{rows}</table></details>")
    steps = "".join(f"<tr><td class='n'><b>{f.n}</b></td><td>{html.escape(spec.node(f.src).title)} → {html.escape(spec.node(f.dst).title)}</td>"
                    f"<td>{html.escape(f.text)}</td></tr>" for f in spec.flows)
    return (f"<section id='{spec.id}'><h2>{html.escape(spec.title)}</h2><p class='sub'>{html.escape(spec.subtitle)}</p>"
            f"{archlib.interactive_html(spec, uid)}"
            f"<p class='dl'>Download: <a href='svg/{spec.id}.svg'>animated SVG</a> · <a href='drawio/{spec.id}.drawio'>draw.io (editable)</a></p>"
            f"<details open><summary>The numbered steps</summary><table><tr><th>#</th><th>From → to</th><th>What happens</th></tr>{steps}</table></details>"
            f"{stages_note}</section>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec_file")
    ap.add_argument("--out", default="docs/architecture")
    ap.add_argument("--title", default="Architecture")
    ap.add_argument("--intro", default="Interactive, numbered architecture diagrams. Press ▶ to follow each flow, or build the system up stage by stage.")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--no-stages", action="store_true")
    ap.add_argument("--no-html", action="store_true")
    a = ap.parse_args()
    specs = load_specs(Path(a.spec_file).resolve())
    if a.only:
        specs = [s for s in specs if s.id in a.only]
    out = Path(a.out)
    (out / "svg").mkdir(parents=True, exist_ok=True)
    (out / "drawio").mkdir(parents=True, exist_ok=True)
    for spec in specs:
        validate(spec)
        (out / "svg" / f"{spec.id}.svg").write_text(archlib.render_svg(spec), encoding="utf-8")
        (out / "drawio" / f"{spec.id}.drawio").write_text(archlib.render_drawio(spec), encoding="utf-8")
        n_st = 0
        if spec.stages and not a.no_stages:
            for st in spec.stages:
                svg = archlib.render_svg(spec, stage=st.k, title=f"Our map so far · {st.parts}: {st.title}",
                                         subtitle=f"New at this stop (pink): {st.blurb}. Solid = already built · faded = still to come.")
                (out / "svg" / f"{spec.id}-stage-{st.k:02d}.svg").write_text(svg, encoding="utf-8")
                n_st += 1
        print(f"  {spec.id}: {len(spec.nodes)} nodes · {len(spec.groups)} groups · {len(spec.flows)} flows · {n_st} stage maps")
    if not a.no_html:
        nav = "".join(f"<a href='#{s.id}'>{html.escape(s.title.split(' — ')[0].split(':')[0])}</a>" for s in specs)
        page = PAGE.format(title=html.escape(a.title), intro=html.escape(a.intro), nav=nav,
                           sections="".join(section(s, f"av{i}") for i, s in enumerate(specs)),
                           archviz_css=archlib.ARCHVIZ_CSS, archviz_js=archlib.ARCHVIZ_JS)
        (out / "index.html").write_text(page, encoding="utf-8")
        print(f"  index.html ({(out / 'index.html').stat().st_size // 1024} KB) - open it in a browser or publish the folder")


if __name__ == "__main__":
    main()
