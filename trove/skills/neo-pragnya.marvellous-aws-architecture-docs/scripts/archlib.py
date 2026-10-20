"""archlib - architecture diagrams as code, AWS-reference style, with numbered and animated flows.

Why: hand-placing coordinates in draw.io does not scale and drifts from the code. Here a diagram is DATA:
nodes on a grid, groups as grid rectangles, numbered flows between nodes, and build stages (which notebook
part introduces what). The engine computes every pixel, routes orthogonal connectors, places step badges,
writes a numbered legend, and emits:

* render_svg(spec)                    - full diagram; flows light up one after another (pure CSS, works in <img>)
* render_svg(spec, stage=k)           - "the map so far": built = solid, new = glowing + marching ants, future = ghosted
* render_svg(spec, stage=k, teardown) - deleted resources struck through
* render_drawio(spec)                 - editable .drawio using draw.io's native AWS shapes (mxgraph.aws4.*)
* interactive_html(spec, uid)         - deck widget: play/step through flows, scrub through build stages

Icons: official AWS Architecture Icons etc. (see assets/icons/SOURCE.md and CATALOG.md). Resolution order:
$ARCHLIB_ICONS, <this file's folder>/icons, <skill>/assets/icons. An unknown icon key draws a text box (with a warning).

Part of the "Marvellous AWS Architectures Docs" skill.
"""
from __future__ import annotations

import base64
import html
import re
import math
from dataclasses import dataclass, field
from pathlib import Path

import os
import sys as _sys


def _icons_dir() -> Path:
    here = Path(__file__).resolve().parent
    for cand in (os.environ.get("ARCHLIB_ICONS"), here / "icons", here.parent / "assets" / "icons"):
        if cand and Path(cand).is_dir():
            return Path(cand)
    return here / "icons"


ICONS = _icons_dir()

# ----------------------------------------------------------------------------------------------- model
CW, CH = 168, 128          # grid cell (px)
PAD = 36                   # canvas padding
ICON = 54                  # icon size (px)
LEGEND_W = 430

PALETTE = {
    "ink": "#232F3E", "muted": "#5F6B7A", "line": "#545B64", "accent": "#FF9900", "new": "#E7157B",
    "badge": "#232F3E", "cloud": "#232F3E", "region": "#00A4A6", "vpc": "#8C4FFF", "subnet": "#7AA116",
    "cluster": "#ED7100", "logic": "#879196", "actor": "#232F3E", "box": "#F2F3F3",
}

DRAWIO_SHAPE = {   # icon key -> draw.io aws4 resource icon (fill colour by AWS category)
    "sagemaker": ("sagemaker", "#01A88D"), "sagemaker-notebook": ("sagemaker_notebook", "#01A88D"),
    "bedrock": ("bedrock", "#01A88D"), "s3": ("s3", "#7AA116"), "s3-bucket": ("s3", "#7AA116"),
    "dynamodb": ("dynamodb", "#C925D1"), "cloudwatch": ("cloudwatch_2", "#E7157B"), "cloudwatch-logs": ("cloudwatch_2", "#E7157B"),
    "cloudformation": ("cloudformation", "#E7157B"), "codebuild": ("codebuild", "#C925D1"), "ecr": ("ecr", "#ED7100"),
    "eks": ("eks", "#ED7100"), "ec2": ("ec2", "#ED7100"), "lambda": ("lambda", "#ED7100"), "lambda-fn": ("lambda", "#ED7100"),
    "secrets": ("secrets_manager", "#DD344C"), "iam": ("identity_and_access_management", "#DD344C"),
    "iam-role": ("identity_and_access_management", "#DD344C"), "scheduler": ("eventbridge", "#E7157B"),
    "sts": ("identity_and_access_management", "#DD344C"), "vpc": ("vpc", "#8C4FFF"),
    "api-gateway": ("api_gateway", "#E7157B"), "cloudfront": ("cloudfront", "#8C4FFF"), "route53": ("route_53", "#8C4FFF"),
    "sqs": ("sqs", "#E7157B"), "sns": ("sns", "#E7157B"), "step-functions": ("step_functions", "#E7157B"),
    "cognito": ("cognito", "#DD344C"), "waf": ("waf", "#DD344C"), "kms": ("key_management_service", "#DD344C"),
    "athena": ("athena", "#8C4FFF"), "glue": ("glue", "#8C4FFF"), "redshift": ("redshift", "#8C4FFF"),
    "rds": ("rds", "#C925D1"), "aurora": ("aurora", "#C925D1"), "ecs": ("ecs", "#ED7100"), "fargate": ("fargate", "#ED7100"),
    "cloudtrail": ("cloudtrail", "#E7157B"), "ssm": ("systems_manager", "#E7157B"),
}


@dataclass
class Node:
    id: str
    icon: str | None          # key in diagrams/icons, or None for a text box
    title: str
    sub: str = ""
    x: float = 0              # grid column (centre)
    y: float = 0              # grid row (centre)
    stage: int = 0            # build stage that introduces it
    deleted_at: int | None = None   # stage at which teardown removes it (None = kept)
    body: list[str] = field(default_factory=list)   # card body lines -> renders a CARD (coloured header + text)
    color: str | None = None  # card header / box accent colour (default: AWS squid ink)
    w: float = 0              # card/box width in grid cells (0 = auto)
    h: float = 0              # card height in grid rows (0 = auto from body)


@dataclass
class Group:
    id: str
    title: str
    x0: float
    y0: float
    x1: float
    y1: float
    style: str = "logic"      # cloud | region | vpc | subnet | cluster | logic
    stage: int = 0
    icon: str | None = None


@dataclass
class Flow:
    n: int                    # step number shown in the badge and legend
    src: str
    dst: str
    text: str                 # legend sentence
    label: str = ""           # short on-diagram label
    stage: int = 0
    sp: str | None = None     # source side: l r t b (auto if None)
    dp: str | None = None     # destination side
    mid: float = 0.5          # where the elbow sits (fraction between the two ports)
    bidir: bool = False
    dashed: bool = False
    badge_at: float = 0.22    # badge position along the path (0..1)
    via: float | None = None  # absolute grid x (for l/r ports) or y (for t/b ports) of the elbow line - routes through gaps
    so: float = 0             # px offset of the source port along its side (separates arrows sharing a side)
    do: float = 0             # px offset of the destination port
    packet: str = ""          # text carried by the animated packet ("SQL", "JWT", "spans"); empty = a plain dot
    color: str | None = None  # line colour, e.g. "#D13212" for a forbidden/failure path, "#1D8102" for the fix


@dataclass
class Stage:
    k: int
    title: str
    parts: str                # e.g. "Part 2"
    blurb: str = ""


@dataclass
class Spec:
    id: str
    title: str
    subtitle: str
    nodes: list[Node]
    flows: list[Flow]
    groups: list[Group] = field(default_factory=list)
    stages: list[Stage] = field(default_factory=list)
    cols: float = 10
    rows: float = 7
    teardown_stage: int | None = None

    def node(self, nid: str) -> Node:
        return next(n for n in self.nodes if n.id == nid)


# ----------------------------------------------------------------------------------------------- geometry
_OY = [70.0]               # header offset (px), set per spec so groups above row 0 never collide with the title
_BASE = [70.0]             # 70 = title + subtitle; 108 when the live caption bar is shown


def _setup(spec) -> None:
    ys = [g.y0 for g in spec.groups] + [n.y - (_card_size(n)[1] / CH / 2 - 0.3 if _is_card(n) else 0) for n in spec.nodes]
    _OY[0] = _BASE[0] + max(0.0, -(min(ys) - 0.0)) * CH + (24 if min(ys) < 0 else 0)


def _is_card(n) -> bool:
    return bool(n.body)


def _card_size(n) -> tuple[float, float]:
    """px width/height of a card (or a wide text box)."""
    w = (n.w or 1.55) * CW - 18
    chars = max(18, int((w - 20) / 6.7))
    lines = sum(len(_wrap(b, chars)) for b in n.body)
    h_auto = 36 + 16 * lines + (14 if n.sub else 6)
    return w, max(h_auto, (n.h * CH - 14) if n.h else 0)


def _box_size(n) -> tuple[float, float]:
    return ((n.w * CW - 20) if n.w else 128), 44


def _extra_h() -> float:
    return _OY[0] - 70


def _px(gx: float, gy: float) -> tuple[float, float]:
    return PAD + gx * CW + CW / 2, PAD + _OY[0] + gy * CH + CH / 2


def _port(n: Node, side: str, off: float = 0) -> tuple[float, float]:
    cx, cy = _px(n.x, n.y)
    if _is_card(n):
        w, h = _card_size(n)
        hx, hy, lab = w / 2 + 4, h / 2 + 4, 0
    elif n.icon is None:                     # text box, label inside
        bw, bh = _box_size(n)
        hx, hy, lab = bw / 2 + 4, bh / 2 + 4, 0
    else:                                     # icon with its label underneath
        hx = hy = ICON / 2 + 4
        lab = 28
    return {"l": (cx - hx, cy + off), "r": (cx + hx, cy + off), "t": (cx + off, cy - hy), "b": (cx + off, cy + hy + lab)}[side]


def _auto_sides(a: Node, b: Node) -> tuple[str, str]:
    dx, dy = b.x - a.x, b.y - a.y
    if abs(dx) >= abs(dy):
        return ("r", "l") if dx >= 0 else ("l", "r")
    return ("b", "t") if dy >= 0 else ("t", "b")


def route(spec: Spec, f: Flow) -> list[tuple[float, float]]:
    a, b = spec.node(f.src), spec.node(f.dst)
    sa, sb = f.sp, f.dp
    if not (sa and sb):
        auto = _auto_sides(a, b)
        sa, sb = sa or auto[0], sb or auto[1]
    p, q = _port(a, sa, f.so), _port(b, sb, f.do)
    if sa in "lr" and sb in "lr":
        if abs(p[1] - q[1]) < 1:
            return [p, q]
        mx = _px(f.via, 0)[0] if f.via is not None else p[0] + (q[0] - p[0]) * f.mid
        return [p, (mx, p[1]), (mx, q[1]), q]
    if sa in "tb" and sb in "tb":
        if abs(p[0] - q[0]) < 1:
            return [p, q]
        my = _px(0, f.via)[1] if f.via is not None else p[1] + (q[1] - p[1]) * f.mid
        return [p, (p[0], my), (q[0], my), q]
    if sa in "lr":                       # horizontal then vertical
        return [p, (q[0], p[1]), q]
    return [p, (p[0], q[1]), q]          # vertical then horizontal


def _length(pts):
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def _point_at(pts, t):
    target, acc = _length(pts) * t, 0.0
    for i in range(len(pts) - 1):
        seg = math.dist(pts[i], pts[i + 1])
        if acc + seg >= target and seg:
            r = (target - acc) / seg
            return pts[i][0] + (pts[i + 1][0] - pts[i][0]) * r, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * r
        acc += seg
    return pts[-1]


def _d(pts):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return lines + ([cur] if cur else [])


_ICON_CACHE: dict[str, str] = {}
_WARNED: set[str] = set()


def has_icon(key: str | None) -> bool:
    ok = bool(key) and (ICONS / f"{key}.png").exists()
    if key and not ok and key not in _WARNED:
        _WARNED.add(key)
        print(f"archlib: no icon '{key}' in {ICONS} - drawing a text box (see CATALOG.md or scripts/fetch_icons.py --add)",
              file=_sys.stderr)
    return ok


def _icon_data(key: str) -> str:
    if key not in _ICON_CACHE:
        _ICON_CACHE[key] = base64.b64encode((ICONS / f"{key}.png").read_bytes()).decode()
    return _ICON_CACHE[key]


def _normalise(spec) -> None:
    """Unknown icon keys become text boxes so a typo never breaks a build."""
    for n in spec.nodes:
        if n.icon and not has_icon(n.icon):
            n.icon = None
    for g in spec.groups:
        if g.icon and not has_icon(g.icon):
            g.icon = None


# ----------------------------------------------------------------------------------------------- SVG
GROUP_STYLE = {
    "cloud": dict(stroke=PALETTE["cloud"], dash="", fill="none", width=1.6, title=PALETTE["cloud"]),
    "region": dict(stroke=PALETTE["region"], dash="6 4", fill="none", width=1.4, title=PALETTE["region"]),
    "vpc": dict(stroke=PALETTE["vpc"], dash="", fill="none", width=1.4, title=PALETTE["vpc"]),
    "subnet": dict(stroke=PALETTE["subnet"], dash="", fill="#F2F8E9", width=1.2, title="#3F6B0E"),
    "cluster": dict(stroke=PALETTE["cluster"], dash="6 4", fill="#FFF7EF", width=1.4, title="#B35400"),
    "logic": dict(stroke=PALETTE["logic"], dash="5 4", fill="none", width=1.2, title="#545B64"),
}


def _group_rect(g: Group):
    x0, y0 = _px(g.x0, g.y0)
    x1, y1 = _px(g.x1, g.y1)
    return x0 - CW / 2 + 10, y0 - CH / 2 + 4, (x1 - x0) + CW - 20, (y1 - y0) + CH - 8


def _extent(spec: Spec) -> tuple[float, float]:
    """Grid size actually needed: never clip a label, never let a group run into the legend."""
    cols = max([spec.cols] + [g.x1 + 1.12 for g in spec.groups] +
               [n.x + max(1.0, (_card_size(n)[0] / CW / 2 + 0.6) if _is_card(n) else 1.0) for n in spec.nodes])
    rows = max([spec.rows] + [g.y1 + 1.0 for g in spec.groups] +
               [n.y + max(1.2, (_card_size(n)[1] / CH / 2 + 0.6) if _is_card(n) else 1.2) for n in spec.nodes])
    for f in spec.flows:                     # a lane routed outside the nodes still needs canvas
        if f.via is not None and (f.sp or "") in "lr" and f.sp:
            cols = max(cols, f.via + 0.35)
        elif f.via is not None and f.sp in ("t", "b"):
            rows = max(rows, f.via + 0.35)
    return cols, rows


def canvas_size(spec: Spec, legend: bool, caption: bool = False) -> tuple[int, int]:
    _normalise(spec)
    _BASE[0] = 108.0 if caption else 70.0
    _setup(spec)
    cols, rows = _extent(spec)
    w = PAD * 2 + cols * CW + (LEGEND_W + 20 if legend else 0)
    h = PAD * 2 + _OY[0] + rows * CH
    if legend:
        lines = sum(len(_wrap(f.text, 58)) for f in spec.flows) * 15 + len(spec.flows) * 9 + 120
        h = max(h, lines)
    return int(w), int(h)


def _spot(attr: str, on: str, off: str, i: int, step: float, total: float) -> str:
    """SMIL: hold `on` while step i is playing, `off` otherwise - the same clock as the packets and the caption."""
    a = step / total
    return (f'<animate attributeName="{attr}" values="{on};{on};{off};{off}" keyTimes="0;{a * .97:.4f};{a:.4f};1" '
            f'dur="{total:.2f}s" begin="{i * step:.2f}s" repeatCount="indefinite"/>')


def render_svg(spec: Spec, stage: int | None = None, legend: bool = True, uid: str | None = None,
               animate: bool = True, title: str | None = None, subtitle: str | None = None,
               step: float = 2.4) -> str:
    """stage=None -> the complete system, LIVE: each numbered flow in turn sends a glowing packet along its arrow,
    the destination pings on arrival, a caption bar narrates the step and a progress bar runs (SMIL + CSS, so it
    animates even as an <img>). stage=k -> the map so far: built = solid, new = pink with looping packets, future =
    faded, torn down = crossed. animate=False -> a still image (used by the interactive widget, which animates itself)."""
    uid = uid or spec.id + (f"-s{stage}" if stage is not None else "")
    uid = re.sub(r"[^A-Za-z0-9_-]", "-", uid)
    if not uid[0].isalpha():
        uid = "av-" + uid            # CSS class names and keyframes may not start with a digit
    live = stage is None and animate
    W, H = canvas_size(spec, legend, caption=live)      # also sets the header offset
    teardown = spec.teardown_stage is not None and stage is not None and stage >= spec.teardown_stage
    cw = PAD + _extent(spec)[0] * CW                     # right edge of the drawing area (legend starts after)

    def state(item_stage, deleted_at=None):
        if stage is None:
            return "built"
        if item_stage == stage:
            return "new"
        if teardown and deleted_at is not None and stage >= deleted_at:
            return "deleted"
        return "built" if item_stage < stage else "future"

    colors = sorted({f.color for f in spec.flows if f.color})
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" '
           f'width="{W}" height="{H}" font-family="Amazon Ember, Inter, Arial, Helvetica, sans-serif" class="archviz-svg" '
           f'data-uid="{uid}" role="img" aria-label="{html.escape(spec.title)}">']
    out.append(f"<title>{html.escape(title or spec.title)}</title>")
    out.append("<defs>")
    for k in sorted({n.icon for n in spec.nodes if n.icon and not _is_card(n)}):
        out.append(f'<image id="{uid}-ic-{k}" width="{ICON}" height="{ICON}" href="data:image/png;base64,{_icon_data(k)}"/>')
    for k in sorted({g.icon for g in spec.groups if g.icon} | {n.icon for n in spec.nodes if n.icon and _is_card(n)}):
        out.append(f'<image id="{uid}-is-{k}" width="22" height="22" href="data:image/png;base64,{_icon_data(k)}"/>')
    marks = [("a", PALETTE["line"]), ("n", PALETTE["new"]), ("h", PALETTE["accent"])] + [(f"c{i}", c) for i, c in enumerate(colors)]
    for name, col in marks:
        out.append(f'<marker id="{uid}-m{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                   f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>')
    out.append(f'<filter id="{uid}-glow" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="0" dy="0" '
               f'stdDeviation="4" flood-color="{PALETTE["accent"]}" flood-opacity=".9"/></filter>')
    out.append(f'<filter id="{uid}-shadow" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="2" '
               f'stdDeviation="3" flood-color="#0F1B2D" flood-opacity=".12"/></filter>')
    out.append("</defs>")

    n_flows = max(len(spec.flows), 1)
    total = n_flows * step
    css = [f"""
.{uid} text{{fill:{PALETTE['ink']}}}
.{uid} .fl .ln{{fill:none;stroke:{PALETTE['line']};stroke-width:1.7}}
.{uid} .fl.dsh .ln{{stroke-dasharray:5 4}}
.{uid} .fl .ant{{fill:none;stroke:{PALETTE['accent']};stroke-width:3;stroke-dasharray:7 11;opacity:0}}
.{uid} .bdg circle{{fill:{PALETTE['badge']}}}
.{uid} .bdg text{{fill:#fff;font-weight:700;font-size:12px}}
.{uid} .future{{opacity:.13;filter:grayscale(1)}}
.{uid} .deleted{{opacity:.35;filter:grayscale(1)}}
.{uid} .new .ln{{stroke:{PALETTE['new']};stroke-width:2.4}}
.{uid} .new .ant{{opacity:1;stroke:{PALETTE['new']};animation:{uid}-ants 1.1s linear infinite}}
.{uid} .new .bdg circle{{fill:{PALETTE['new']}}}
.{uid} .nd.new .halo{{opacity:1;animation:{uid}-pulse 1.6s ease-in-out infinite}}
.{uid} .nd .halo{{opacity:0;fill:none;stroke:{PALETTE['new']};stroke-width:3}}
.{uid} .lg.new text{{fill:{PALETTE['new']}}}
.{uid} .lg.future{{opacity:.25}}
.{uid} .cap text{{fill:#fff}}
@keyframes {uid}-ants{{to{{stroke-dashoffset:-36}}}}
@keyframes {uid}-pulse{{0%,100%{{stroke-opacity:.25}}50%{{stroke-opacity:1}}}}
@media (prefers-reduced-motion:reduce){{.{uid} *{{animation:none!important}}}}
"""]
    for i, c in enumerate(colors):
        css.append(f".{uid} .fl.c{i} .ln{{stroke:{c};stroke-width:2.2}}")
    if live:
        css.append(f".{uid} .fl .ant{{animation:{uid}-ants 1.1s linear infinite}}")
    out.append(f"<style>{''.join(css)}</style>")
    out.append(f'<g class="{uid}">')
    out.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF"/>')
    out.append(f'<text x="{PAD}" y="{PAD + 8}" font-size="22" font-weight="700">{html.escape(title or spec.title)}</text>')
    out.append(f'<text x="{PAD}" y="{PAD + 32}" font-size="13" fill="{PALETTE["muted"]}">{html.escape(subtitle or spec.subtitle)}</text>')

    # live caption bar: narrates the current step, with a progress bar
    if live:
        bx, by, bw, bh = PAD, PAD + 46, cw - PAD - 12, 32
        out.append(f'<g class="cap"><rect x="{bx}" y="{by}" width="{bw:.0f}" height="{bh}" rx="7" fill="#232F3E"/>')
        out.append(f'<rect x="{bx}" y="{by + bh - 4}" width="0" height="4" rx="2" fill="{PALETTE["accent"]}">'
                   f'<animate attributeName="width" values="0;{bw:.0f}" dur="{total:.2f}s" repeatCount="indefinite"/></rect>')
        out.append(f'<text x="{bx + 12}" y="{by + 21}" font-size="13" font-weight="700" style="fill:{PALETTE["accent"]}">▶ NOW</text>')
        chars = int((bw - 90) / 7.2)
        for i, f in enumerate(spec.flows):
            a = step / total
            txt = f"{f.n} · {f.text}"
            txt = txt if len(txt) <= chars else txt[:chars - 1] + "…"
            out.append(f'<text x="{bx + 72}" y="{by + 21}" font-size="13.5" opacity="0">{html.escape(txt)}'
                       f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;{a * .04:.4f};{a * .96:.4f};{a:.4f};1" '
                       f'dur="{total:.2f}s" begin="{i * step:.2f}s" repeatCount="indefinite"/></text>')
        out.append("</g>")

    # groups
    for g in spec.groups:
        st = GROUP_STYLE[g.style]
        x, y, w, h = _group_rect(g)
        cls = state(g.stage)
        out.append(f'<g class="gp {cls}" data-id="{g.id}" data-stage="{g.stage}">')
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="4" fill="{st["fill"]}" '
                   f'stroke="{st["stroke"]}" stroke-width="{st["width"]}" stroke-dasharray="{st["dash"]}"/>')
        tx = x + 10
        if g.icon:
            out.append(f'<use href="#{uid}-is-{g.icon}" x="{x + 6:.1f}" y="{y + 3:.1f}"/>')
            tx = x + 34
        out.append(f'<text x="{tx:.1f}" y="{y + 19:.1f}" font-size="12.5" font-weight="700" fill="{st["title"]}">'
                   f'{html.escape(g.title)}</text></g>')

    # flows (lines under nodes)
    paths = {}
    for f in spec.flows:
        pts = route(spec, f)
        paths[f.n] = pts
        cls = state(f.stage, min([x for x in (spec.node(f.src).deleted_at, spec.node(f.dst).deleted_at) if x is not None], default=None))
        ck = f"c{colors.index(f.color)}" if f.color else ""
        mk = f"url(#{uid}-m{'n' if cls == 'new' else (ck or 'a')})"
        out.append(f'<g class="fl f{f.n} {cls} {ck}{" dsh" if f.dashed else ""}" data-n="{f.n}" data-stage="{f.stage}">')
        ms = f' marker-start="{mk}"' if f.bidir else ""
        out.append(f'<path class="ln" d="{_d(pts)}" marker-end="{mk}"{ms}/>')
        idx = spec.flows.index(f)
        if live:
            out.append(f'<path class="ant" d="{_d(pts)}" opacity="0">{_spot("opacity", "1", "0", idx, step, total)}</path>')
        else:
            out.append(f'<path class="ant" d="{_d(pts)}"/>')
        if f.label:
            mx, my = _point_at(pts, .55)
            out.append(f'<text x="{mx:.1f}" y="{my - 6:.1f}" font-size="10.5" text-anchor="middle" fill="{f.color or PALETTE["muted"]}" '
                       f'font-style="italic">{html.escape(f.label)}</text>')
        bx, by = _point_at(pts, f.badge_at)
        spot = _spot("fill", PALETTE["accent"], PALETTE["badge"], idx, step, total) if live else ""
        out.append(f'<g class="bdg"><circle cx="{bx:.1f}" cy="{by:.1f}" r="11">{spot}</circle><text x="{bx:.1f}" y="{by + 4:.1f}" '
                   f'text-anchor="middle">{f.n}</text></g></g>')

    # nodes
    for n in spec.nodes:
        cx, cy = _px(n.x, n.y)
        cls = state(n.stage, n.deleted_at)
        out.append(f'<g class="nd {cls}" data-id="{n.id}" data-stage="{n.stage}">')
        if _is_card(n):
            cwid, chei = _card_size(n)
            x0, y0 = cx - cwid / 2, cy - chei / 2
            col = n.color or PALETTE["ink"]
            out.append(f'<rect class="halo" x="{x0 - 6:.1f}" y="{y0 - 6:.1f}" width="{cwid + 12:.1f}" height="{chei + 12:.1f}" rx="12"/>')
            out.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{cwid:.1f}" height="{chei:.1f}" rx="9" fill="#FFFFFF" stroke="{col}" '
                       f'stroke-width="1.5" filter="url(#{uid}-shadow)"/>')
            out.append(f'<path d="M{x0:.1f},{y0 + 28:.1f} V{y0 + 9:.1f} Q{x0:.1f},{y0:.1f} {x0 + 9:.1f},{y0:.1f} H{x0 + cwid - 9:.1f} '
                       f'Q{x0 + cwid:.1f},{y0:.1f} {x0 + cwid:.1f},{y0 + 9:.1f} V{y0 + 28:.1f} Z" fill="{col}"/>')
            tx = x0 + 10
            if n.icon:
                out.append(f'<rect x="{x0 + 5:.1f}" y="{y0 + 3:.1f}" width="22" height="22" rx="4" fill="#FFFFFF"/>')
                out.append(f'<use href="#{uid}-is-{n.icon}" x="{x0 + 5:.1f}" y="{y0 + 3:.1f}"/>')
                tx = x0 + 34
            out.append(f'<text x="{tx:.1f}" y="{y0 + 19:.1f}" font-size="13" font-weight="700" style="fill:#FFFFFF">'
                       f'{html.escape(n.title)}</text>')
            chars = max(18, int((cwid - 20) / 6.7))
            yy = y0 + 46
            for b in n.body:
                for ln in _wrap(b, chars):
                    out.append(f'<text x="{x0 + 10:.1f}" y="{yy:.1f}" font-size="12.3">{html.escape(ln)}</text>')
                    yy += 16
            if n.sub:
                out.append(f'<text x="{x0 + cwid - 8:.1f}" y="{y0 + chei - 8:.1f}" font-size="10.5" font-weight="700" '
                           f'text-anchor="end" fill="{col}">{html.escape(n.sub)}</text>')
        elif n.icon:
            out.append(f'<rect class="halo" x="{cx - ICON / 2 - 7:.1f}" y="{cy - ICON / 2 - 7:.1f}" width="{ICON + 14}" height="{ICON + 14}" rx="10"/>')
            out.append(f'<use href="#{uid}-ic-{n.icon}" x="{cx - ICON / 2:.1f}" y="{cy - ICON / 2:.1f}"/>')
        else:
            bw, bh = _box_size(n)
            out.append(f'<rect class="halo" x="{cx - bw / 2 - 6:.1f}" y="{cy - bh / 2 - 6:.1f}" width="{bw + 12:.1f}" height="{bh + 12:.1f}" rx="12"/>')
            out.append(f'<rect x="{cx - bw / 2:.1f}" y="{cy - bh / 2:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="8" '
                       f'fill="{PALETTE["box"]}" stroke="{n.color or "#AAB7B8"}" stroke-width="{1.6 if n.color else 1}"/>')
        if not _is_card(n):
            lines = _wrap(n.title, 22 if n.icon or not n.w else int(_box_size(n)[0] / 7.5))
            nsub = min(len(_wrap(n.sub, 26 if n.icon or not n.w else int(_box_size(n)[0] / 6.5))), 2) if n.sub else 0
            ty = cy + ICON / 2 + 15 if n.icon else cy + 4.5 - ((len(lines) - 1) * 13 + nsub * 12) / 2
            for i, ln in enumerate(lines):
                out.append(f'<text x="{cx:.1f}" y="{ty + i * 13:.1f}" font-size="12" font-weight="700" text-anchor="middle">'
                           f'{html.escape(ln)}</text>')
            for i, ln in enumerate(_wrap(n.sub, 26 if n.icon or not n.w else int(_box_size(n)[0] / 6.5))[:2]):
                out.append(f'<text x="{cx:.1f}" y="{ty + len(lines) * 13 + i * 12:.1f}" font-size="10.5" font-style="italic" '
                           f'text-anchor="middle" fill="{PALETTE["muted"]}">{html.escape(ln)}</text>')
        if cls == "deleted":
            out.append(f'<path d="M{cx - 30:.1f},{cy - 30:.1f} L{cx + 30:.1f},{cy + 30:.1f} M{cx + 30:.1f},{cy - 30:.1f} '
                       f'L{cx - 30:.1f},{cy + 30:.1f}" stroke="#D13212" stroke-width="4" stroke-linecap="round"/>')
        out.append("</g>")

    # packets (on top of everything): live = one at a time in step order; stage map = new flows loop continuously
    def packet(f, begin, dur, window, loop_dot_only=False):
        pts = paths[f.n]
        d = _d(pts)
        a = window
        col = f.color or (PALETTE["new"] if stage is not None else PALETTE["accent"])
        lab = ""
        if f.packet:
            tw = 7 * len(f.packet) + 14
            lab = (f'<rect x="{-tw / 2:.1f}" y="-27" width="{tw:.1f}" height="17" rx="8.5" fill="#232F3E"/>'
                   f'<text x="0" y="-14.5" font-size="10.5" font-weight="700" text-anchor="middle" style="fill:#FFFFFF">'
                   f'{html.escape(f.packet)}</text>')
        out.append(f'<g opacity="0"><circle r="7.5" fill="{col}" stroke="#FFFFFF" stroke-width="2.5" filter="url(#{uid}-glow)"/>{lab}'
                   f'<animateMotion path="{d}" dur="{dur:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite" calcMode="linear" '
                   f'keyPoints="0;1;1" keyTimes="0;{a:.4f};1"/>'
                   f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.0001;{a:.4f};{min(a + 0.0002, 0.9999):.4f};1" '
                   f'dur="{dur:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite"/></g>')
        # arrival ping on the destination
        dn = spec.node(f.dst)
        px, py = pts[-1]
        t1, t2 = a * 0.97, min(a * 1.45, 0.999)
        out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="10" fill="none" stroke="{col}" stroke-width="3" opacity="0">'
                   f'<animate attributeName="r" values="10;10;34;34" keyTimes="0;{t1:.4f};{t2:.4f};1" dur="{dur:.2f}s" '
                   f'begin="{begin:.2f}s" repeatCount="indefinite"/>'
                   f'<animate attributeName="opacity" values="0;0;.9;0;0" keyTimes="0;{t1 - 0.0001:.4f};{t1:.4f};{t2:.4f};1" '
                   f'dur="{dur:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite"/></circle>')

    if live:
        for i, f in enumerate(spec.flows):
            packet(f, i * step, total, (step * 0.82) / total)
    elif stage is not None and animate:
        new = [f for f in spec.flows if f.stage == stage]
        for j, f in enumerate(new):
            packet(f, j * 0.6, 2.6, 0.62)

    # legend
    if legend:
        lx = cw + 24
        out.append(f'<rect x="{lx - 12}" y="0" width="{W - lx + 12}" height="{H}" fill="#F2F3F3"/>')
        y = PAD + 8
        head = "How it flows" if stage is None else f"Map so far: {_stage_title(spec, stage)}"
        out.append(f'<text x="{lx}" y="{y}" font-size="15" font-weight="700">{html.escape(head)}</text>')
        y += 24
        for f in spec.flows:
            cls = state(f.stage)
            lines = _wrap(f.text, 58)
            spot = _spot("fill", PALETTE["accent"], PALETTE["badge"], f.n - 1, step, total) if live else ""
            out.append(f'<g class="lg l{f.n} {cls}" data-n="{f.n}"><g class="lb"><circle cx="{lx + 11}" cy="{y + 4}" r="11" '
                       f'fill="{PALETTE["new"] if cls == "new" else PALETTE["badge"]}">{spot}</circle><text x="{lx + 11}" y="{y + 8}" '
                       f'font-size="12" font-weight="700" text-anchor="middle" fill="#fff" style="fill:#fff">{f.n}</text></g>')
            for i, ln in enumerate(lines):
                out.append(f'<text x="{lx + 30}" y="{y + 8 + i * 15}" font-size="12.5">{html.escape(ln)}</text>')
            out.append("</g>")
            y += len(lines) * 15 + 9
    out.append("</g></svg>")
    return "\n".join(out)


def _stage_title(spec: Spec, k: int) -> str:
    s = next((s for s in spec.stages if s.k == k), None)
    return f"{s.parts} · {s.title}" if s else f"stage {k}"


# ----------------------------------------------------------------------------------------------- draw.io
def render_drawio(spec: Spec) -> str:
    _normalise(spec)
    _setup(spec)
    cells, eid = [], 2
    for g in spec.groups:
        x, y, w, h = _group_rect(g)
        st = GROUP_STYLE[g.style]
        style = (f"rounded=1;arcSize=2;whiteSpace=wrap;html=1;fillColor={st['fill'] if st['fill'] != 'none' else 'none'};"
                 f"strokeColor={st['stroke']};dashed={1 if st['dash'] else 0};verticalAlign=top;align=left;spacingLeft=8;"
                 f"fontStyle=1;fontColor={st['title']};container=0;")
        cells.append(f'<mxCell id="g_{g.id}" value="{html.escape(g.title)}" style="{style}" vertex="1" parent="1">'
                     f'<mxGeometry x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" as="geometry"/></mxCell>')
    for n in spec.nodes:
        cx, cy = _px(n.x, n.y)
        label = html.escape(n.title + (f"<br><i>{n.sub}</i>" if n.sub else ""))
        if n.icon in DRAWIO_SHAPE:
            res, col = DRAWIO_SHAPE[n.icon]
            style = (f"sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;fillColor={col};strokeColor=#ffffff;"
                     f"dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=12;fontStyle=1;"
                     f"aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res};")
        elif n.icon and not _is_card(n):
            style = (f"shape=image;verticalLabelPosition=bottom;verticalAlign=top;html=1;fontSize=12;fontStyle=1;"
                     f"image=data:image/png,{_icon_data(n.icon)};")
        elif _is_card(n):
            col = n.color or PALETTE["ink"]
            style = (f"swimlane;startSize=26;rounded=1;arcSize=6;html=1;whiteSpace=wrap;fillColor={col};fontColor=#FFFFFF;"
                     f"strokeColor={col};swimlaneFillColor=#FFFFFF;align=left;spacingLeft=8;fontStyle=1;")
        else:
            style = (f"rounded=1;whiteSpace=wrap;html=1;fillColor=#F2F3F3;strokeColor={n.color or '#AAB7B8'};fontStyle=1;")
        if _is_card(n):
            w, h = _card_size(n)
            label = html.escape(n.title)
        elif n.icon:
            w, h = ICON, ICON
        else:
            w, h = _box_size(n)
        cells.append(f'<mxCell id="n_{n.id}" value="{label}" style="{style}" vertex="1" parent="1">'
                     f'<mxGeometry x="{cx - w / 2:.0f}" y="{cy - h / 2:.0f}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        if _is_card(n):
            body = html.escape("<br>".join(html.escape(b) for b in n.body))
            cells.append(f'<mxCell id="nb_{n.id}" value="{body}" style="text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;'
                         f'spacingLeft=8;fontSize=12;" vertex="1" parent="n_{n.id}"><mxGeometry x="0" y="26" width="{w:.0f}" '
                         f'height="{h - 26:.0f}" as="geometry"/></mxCell>')
    for f in spec.flows:
        pts = route(spec, f)
        style = ("edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeColor=#545B64;"
                 f"{'startArrow=block;startFill=1;' if f.bidir else ''}{'dashed=1;' if f.dashed else ''}")
        way = "".join(f'<mxPoint x="{x:.0f}" y="{y:.0f}"/>' for x, y in pts[1:-1])
        cells.append(f'<mxCell id="e{eid}" value="" style="{style}" edge="1" parent="1" source="n_{f.src}" target="n_{f.dst}">'
                     f'<mxGeometry relative="1" as="geometry"><Array as="points">{way}</Array></mxGeometry></mxCell>')
        bx, by = _point_at(pts, f.badge_at)
        cells.append(f'<mxCell id="b{eid}" value="{f.n}" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#232F3E;'
                     f'fontColor=#FFFFFF;strokeColor=none;fontStyle=1;" vertex="1" parent="1"><mxGeometry x="{bx - 11:.0f}" '
                     f'y="{by - 11:.0f}" width="22" height="22" as="geometry"/></mxCell>')
        eid += 1
    W, H = canvas_size(spec, legend=False)
    return (f'<mxfile host="archlib"><diagram name="{html.escape(spec.title)}"><mxGraphModel dx="{W}" dy="{H}" grid="1" '
            f'gridSize="10" page="1" pageWidth="{W}" pageHeight="{H}"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
            + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>")


# ----------------------------------------------------------------------------------------------- deck widget
def interactive_html(spec: Spec, uid: str, start_stage: int | None = None) -> str:
    """The SVG inline plus controls: play/step through the numbered flows, and scrub through build stages."""
    svg = render_svg(spec, stage=None, legend=True, uid=uid, animate=False)
    chips = "".join(f'<button class="av-st" data-k="{s.k}" title="{html.escape(s.blurb)}"><b>{html.escape(s.parts)}</b>'
                    f'{html.escape(s.title)}</button>' for s in spec.stages)
    build = (f'<span class="av-sep"></span><span class="av-lbl">Build it up:</span>{chips}'
             f'<button class="av-st av-all" data-k="all"><b>All</b>complete system</button>') if spec.stages else ""
    start = "" if start_stage is None else f' data-start="{start_stage}"'
    return (f'<div class="archviz" id="{uid}"{start} data-max="{max([s.k for s in spec.stages], default=0)}" '
            f'data-flows="{len(spec.flows)}">'
            f'<div class="av-bar"><button class="av-play" title="play the numbered flow">▶ Play the flow</button>'
            f'<button class="av-prev" title="previous step">‹</button><span class="av-now">all steps</span>'
            f'<button class="av-next" title="next step">›</button>{build}</div>'
            f'<div class="av-cap"></div><div class="av-svg">{svg}</div></div>')


ARCHVIZ_CSS = r"""
.archviz{background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px;box-shadow:var(--shadow);margin:8px 0}
.av-bar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:6px;font-size:13px;color:#232F3E}
.av-bar button{border:1px solid #D5DBDB;background:#F8F9FA;color:#232F3E;border-radius:8px;padding:5px 9px;cursor:pointer;font:inherit;font-size:12.5px}
.av-bar button:hover{border-color:#FF9900}.av-bar .av-play{background:#232F3E;color:#fff;border-color:#232F3E;font-weight:700}
.av-st b{margin-right:5px;color:#E7157B}.av-st.on{background:#FFF0F7;border-color:#E7157B}
.av-now{min-width:90px;text-align:center;font-weight:700}.av-sep{flex:0 0 12px}.av-lbl{color:#5F6B7A}
.av-cap{min-height:22px;font-size:14px;color:#232F3E;padding:2px 4px 6px;font-weight:600}
.av-svg svg{width:100%;height:auto;display:block}
.archviz .fl,.archviz .nd,.archviz .gp,.archviz .lg{transition:opacity .45s, filter .45s}
.archviz.stepping .fl:not(.cur),.archviz.stepping .lg:not(.cur){opacity:.18}
.archviz .fl.cur .ln{stroke:#FF9900!important;stroke-width:3.2!important}
.archviz .fl.cur .ant{opacity:1!important;stroke:#FF9900!important;stroke-dasharray:7 11;animation:avants 1s linear infinite}
.archviz .fl.cur .bdg circle,.archviz .lg.cur .lb circle{fill:#FF9900!important}
.archviz .lg{cursor:pointer}
@keyframes avants{to{stroke-dashoffset:-36}}
.archviz .st-future{opacity:.1!important;filter:grayscale(1)}
.archviz .st-new .ln{stroke:#E7157B!important;stroke-width:2.6!important}
.archviz .st-new .ant{opacity:1!important;stroke:#E7157B!important;stroke-dasharray:7 11;animation:avants 1.1s linear infinite}
.archviz .nd.st-new .halo{opacity:1!important;fill:none;stroke:#E7157B;stroke-width:3;animation:avpulse 1.6s ease-in-out infinite}
.archviz .st-new .bdg circle,.archviz .lg.st-new .lb circle{fill:#E7157B!important}
@keyframes avpulse{0%,100%{stroke-opacity:.25}50%{stroke-opacity:1}}
.archviz .dot{fill:#FF9900;filter:drop-shadow(0 0 4px #FF9900)}
@media (prefers-reduced-motion:reduce){.archviz *{animation:none!important;transition:none!important}}
"""

ARCHVIZ_JS = r"""
document.querySelectorAll('.archviz').forEach(av=>{
 const svg=av.querySelector('svg'),flows=[...svg.querySelectorAll('.fl')].sort((a,b)=>a.dataset.n-b.dataset.n),
  legs=[...svg.querySelectorAll('.lg')],cap=av.querySelector('.av-cap'),now=av.querySelector('.av-now'),
  chips=[...av.querySelectorAll('.av-st')];let i=-1,timer=null,dot=null;
 const text=n=>{const l=legs.find(x=>x.dataset.n==n);return l?[...l.querySelectorAll('text')].slice(1).map(t=>t.textContent).join(' '):''};
 function clearStage(){svg.querySelectorAll('.st-future,.st-new').forEach(e=>e.classList.remove('st-future','st-new'));chips.forEach(c=>c.classList.remove('on'))}
 function stage(k){stop();clearStage();i=-1;av.classList.remove('stepping');flows.forEach(f=>f.classList.remove('cur'));legs.forEach(l=>l.classList.remove('cur'));
  if(k==='all'){chips.find(c=>c.dataset.k==='all')?.classList.add('on');cap.textContent='The complete system: press ▶ to follow every numbered step.';now.textContent='all steps';return}
  k=+k;chips.find(c=>c.dataset.k==k)?.classList.add('on');
  svg.querySelectorAll('[data-stage]').forEach(e=>{const s=+e.dataset.stage;if(s>k)e.classList.add('st-future');else if(s===k)e.classList.add('st-new')});
  legs.forEach(l=>{const f=flows.find(x=>x.dataset.n==l.dataset.n);const s=+f.dataset.stage;if(s>k)l.classList.add('st-future');else if(s===k)l.classList.add('st-new')});
  const ch=chips.find(c=>c.dataset.k==k);cap.textContent=ch?('Map so far — '+ch.querySelector('b').textContent+' · '+ch.textContent.slice(ch.querySelector('b').textContent.length)+' · new pieces glow pink'):'';now.textContent=ch?ch.querySelector('b').textContent:'stage '+k}
 function show(j){clearStage();av.classList.add('stepping');i=(j+flows.length)%flows.length;
  flows.forEach((f,k)=>f.classList.toggle('cur',k===i));const n=flows[i].dataset.n;legs.forEach(l=>l.classList.toggle('cur',l.dataset.n==n));
  now.textContent='step '+n+' / '+flows.length;cap.textContent=n+' · '+text(n);moveDot(flows[i])}
 function moveDot(f){if(dot)dot.remove();const p=f.querySelector('.ln');const L=p.getTotalLength?p.getTotalLength():0;if(!L)return;
  dot=document.createElementNS('http://www.w3.org/2000/svg','circle');dot.setAttribute('r',7);dot.setAttribute('class','dot');svg.querySelector('g').appendChild(dot);
  const t0=performance.now();(function anim(t){if(!dot)return;const k=Math.min(1,((t||performance.now())-t0)/1300);const pt=p.getPointAtLength(L*k);dot.setAttribute('cx',pt.x);dot.setAttribute('cy',pt.y);
   if(k<1)requestAnimationFrame(anim)})(t0)}
 function stop(){if(timer)clearInterval(timer);timer=null;av.querySelector('.av-play').textContent='▶ Play the flow'}
 function play(){if(timer){stop();return}if(i>=flows.length-1)i=-1;show(i+1);timer=setInterval(()=>{if(i>=flows.length-1){stop();return}show(i+1)},2200);
  av.querySelector('.av-play').textContent='⏸ Pause'}
 av.querySelector('.av-play').onclick=e=>{e.stopPropagation();play()};
 av.querySelector('.av-next').onclick=e=>{e.stopPropagation();stop();show(i+1)};
 av.querySelector('.av-prev').onclick=e=>{e.stopPropagation();stop();show(i-1)};
 chips.forEach(c=>c.onclick=e=>{e.stopPropagation();stage(c.dataset.k)});
 legs.forEach(l=>l.onclick=e=>{e.stopPropagation();stop();show(flows.findIndex(f=>f.dataset.n==l.dataset.n))});
 av.archStage=stage;const qs=new URLSearchParams(location.search).get('archstage');stage(qs!==null?qs:(av.dataset.start!==undefined?av.dataset.start:'all'));
});
"""
