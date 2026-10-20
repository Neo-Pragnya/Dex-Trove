"""Life Ikigai Architect - deck engine.

Turns a life spec (JSON, or a .py file defining SPEC) into ONE self-contained, animated HTML presentation:
interactive Ikigai Venn, Pancakrtya wheel, vision/mission cascade, ecosystem flows, roadmaps, scoring heatmaps...

    from ikigai_deck import build_html, load_spec, validate
    spec = load_spec("life.json"); problems = validate(spec); html = build_html(spec, base_dir)

Slide types and their fields: references/spec-reference.md (or `build_deck.py --list-types`).
No third-party dependencies. Output has no external scripts (Google Fonts optional, with system fallbacks).
"""
from __future__ import annotations

import base64
import html as _html
import json
import math
import mimetypes
import pathlib
import re
import runpy

# --------------------------------------------------------------------------------------------- helpers

COLORS = ["love", "good", "need", "paid", "lotus", "indigo", "gold", "acc"]


def esc(s) -> str:
    return _html.escape("" if s is None else str(s), quote=True)


def md(s) -> str:
    """Tiny inline markdown: **bold**, *italic* / _italic_, `code`, newline -> <br>."""
    if s is None:
        return ""
    s = _html.escape(str(s), quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
    s = re.sub(r"(?<![\w])_(?!\s)(.+?)(?<!\s)_(?![\w])", r"<i>\1</i>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s.replace("\n", "<br>")


def plain(s) -> str:
    return re.sub(r"[*_`]", "", str(s or ""))


def col(c, i=0) -> str:
    """Colour key -> CSS var. Accepts a palette key or a literal colour."""
    if not c:
        c = COLORS[i % len(COLORS)]
    if c in COLORS or c in ("warn", "bad", "ok"):
        return f"var(--{c})"
    return esc(c)


def wrap(text: str, n: int) -> list[str]:
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > n:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def lst(items, cls="ticks") -> str:
    if not items:
        return ""
    return f'<ul class="{cls}">' + "".join(f"<li>{md(i)}</li>" for i in items) + "</ul>"


def header(s) -> str:
    out = ""
    if s.get("kicker"):
        out += f'<p class="kicker">{md(s["kicker"])}</p>'
    if s.get("title"):
        out += f'<h2>{md(s["title"])}</h2>'
    if s.get("intro"):
        out += f'<p class="lead">{md(s["intro"])}</p>'
    return out


def footer(s) -> str:
    out = ""
    if s.get("summary"):
        out += f'<blockquote class="f">{md(s["summary"])}</blockquote>'
    if s.get("note"):
        out += f'<p class="note f">{md(s["note"])}</p>'
    return out


def opt(fmt, v, raw=False) -> str:
    """Render fmt with {} -> md(v) (or the raw value), or nothing when v is empty."""
    return fmt.replace("{}", str(v) if raw else md(v)) if v not in (None, "", []) else ""


def tour_btn(label="⏸ Pause") -> str:
    return f'<button class="seltour" type="button">{label}</button>'


# --------------------------------------------------------------------------------------------- art


def mandala(cls="mandala") -> str:
    petals = "".join(
        f'<ellipse cx="0" cy="-118" rx="20" ry="64" transform="rotate({k * 30})"/>' for k in range(12)
    )
    dots = "".join(
        f'<circle cx="{168 * math.cos(math.radians(k * 15)):.1f}" cy="{168 * math.sin(math.radians(k * 15)):.1f}" r="2.6"/>'
        for k in range(24)
    )
    c = [("love", 0, -44), ("good", -44, 0), ("need", 44, 0), ("paid", 0, 44)]
    circles = "".join(f'<circle class="mc" cx="{x}" cy="{y}" r="70" style="fill:var(--v-{k})"/>' for k, x, y in c)
    return f"""<svg class="{cls}" viewBox="-200 -200 400 400" aria-hidden="true">
<circle class="m-ring" r="190"/><g class="m-dots">{dots}</g><g class="m-petals">{petals}</g>
<g class="m-core">{circles}</g><circle class="m-center" r="17"/></svg>"""


# --------------------------------------------------------------------------------------------- slide renderers

R = {}


def slide_type(name, required=()):
    def deco(fn):
        R[name] = (fn, tuple(required))
        return fn

    return deco


@slide_type("hero", ["title"])
def r_hero(s, ctx):
    jp = f'<p class="jp f">{esc(s["jp"])}</p>' if s.get("jp") else ""
    return f"""<div class="hero-wrap"><div class="hero-text">
<p class="kicker f">{md(s.get("kicker"))}</p><h1 class="title">{md(s["title"])}</h1>{jp}
<p class="sub f">{md(s.get("subtitle"))}</p>
{f'<p class="tagline f">{md(s["tagline"])}</p>' if s.get("tagline") else ""}
<p class="hint f">Press <kbd>→</kbd> or <kbd>Space</kbd> · <kbd>M</kbd> menu · <kbd>T</kbd> theme · swipe on phones</p>
</div><div class="hero-art">{mandala()}</div></div>"""


@slide_type("agenda")
def r_agenda(s, ctx):
    chs = [c for c in ctx["chapters"] if c["id"] not in s.get("skip", [])]
    cards = "".join(
        f'<button class="ag f" type="button" data-goto="{esc(c["id"])}" style="--c:{col(c.get("color"), i)}">'
        f'<span class="ag-n">{i + 1:02d}</span><span class="ag-i">{esc(c.get("icon", ""))}</span>'
        f'<b>{md(c["title"])}</b><span>{md(c.get("blurb", ""))}</span></button>'
        for i, c in enumerate(chs)
    )
    return header(s) + f'<div class="agenda">{cards}</div>' + footer(s)


@slide_type("statement")
def r_statement(s, ctx):
    out = header(s)
    if s.get("sanskrit"):
        out += f'<p class="skt f">{esc(s["sanskrit"])}</p>'
    if s.get("quote"):
        out += f'<p class="big-quote f">{md(s["quote"])}</p>'
    if s.get("lines"):
        out += '<div class="st-lines">' + "".join(f'<p class="f">{md(l)}</p>' for l in s["lines"]) + "</div>"
    if s.get("attribution"):
        out += f'<p class="attr f">— {md(s["attribution"])}</p>'
    return out + footer(s)


@slide_type("text")
def r_text(s, ctx):
    out = header(s)
    for p in s.get("paras", []):
        out += f'<p class="para f">{md(p)}</p>'
    if s.get("bullets"):
        out += f'<div class="f">{lst(s["bullets"])}</div>'
    if s.get("quote"):
        out += f'<blockquote class="f">{md(s["quote"])}</blockquote>'
    return out + footer(s)


@slide_type("cards", ["cards"])
def r_cards(s, ctx):
    tone = s.get("tone", "")
    mn = {1: 520, 2: 340, 3: 260, 4: 210, 5: 180}.get(s.get("columns", 3), 240)
    out = header(s) + f'<div class="cards {esc(tone)}" style="--min:{mn}px">'
    for i, c in enumerate(s["cards"]):
        tag = f'<span class="tag">{md(c["tag"])}</span>' if c.get("tag") else ""
        body = f'<p>{md(c["body"])}</p>' if c.get("body") else ""
        extra = ""
        if c.get("remedy"):
            extra = f'<p class="remedy">→ {md(c["remedy"])}</p>'
        if c.get("points"):
            extra += lst(c["points"], "dots")
        cc = col(c.get("color"), i) if (c.get("color") or s.get("rainbow")) else "var(--acc)"
        out += (f'<article class="card f" style="--c:{cc}"><div class="card-h"><span class="ci">{esc(c.get("icon", ""))}</span>'
                f'<h3>{md(c.get("title", ""))}</h3>{tag}</div>{body}{extra}</article>')
    return out + "</div>" + footer(s)


@slide_type("table", ["columns", "rows"])
def r_table(s, ctx):
    hl = set(s.get("highlight", []))
    th = "".join(f"<th>{md(c)}</th>" for c in s["columns"])
    trs = ""
    for i, row in enumerate(s["rows"]):
        trs += f'<tr class="{"hl" if i in hl else ""}">' + "".join(f"<td>{md(c)}</td>" for c in row) + "</tr>"
    cls = "t sm" if s.get("compact") else "t"
    return header(s) + f'<div class="tscroll f"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>' + footer(s)


# ---- Ikigai Venn ------------------------------------------------------------------------------------

VR, VD = 165, 105
VC = {"L": (0, -VD), "G": (-VD, 0), "N": (VD, 0), "P": (0, VD)}
QUAD = {"love": "L", "good": "G", "need": "N", "paid": "P"}
QUAD_DEFAULT = {
    "love": ("What I", "LOVE"), "good": ("What I am", "GOOD AT"),
    "need": ("What the world", "NEEDS"), "paid": ("What I can be", "PAID FOR"),
}
PAIRS = {"passion": ("L G", "PASSION", (-96, -96)), "mission": ("L N", "MISSION", (96, -96)),
         "profession": ("G P", "PROFESSION", (-96, 96)), "vocation": ("N P", "VOCATION", (96, 96))}
LENSES = {  # key: sets, classic feeling, missing circle, anchor, text pos, path
    "t_no_need": ("L G P", "Satisfaction, but feeling of uselessness", "need", (-92, 0), (-262, -236), "M -92 0 C -170 -20 -200 -190 -250 -232"),
    "t_no_paid": ("L G N", "Delight and fullness, but no wealth", "paid", (0, -92), (262, -236), "M 0 -92 C 10 -180 150 -238 250 -238"),
    "t_no_love": ("G N P", "Comfortable, but feeling of emptiness", "love", (0, 92), (-262, 236), "M 0 92 C -10 180 -150 238 -250 238"),
    "t_no_good": ("L N P", "Excitement and complacency, but sense of uncertainty", "good", (92, 0), (262, 222), "M 92 0 C 170 20 200 180 250 222"),
}
LENS_FILL = {"t_no_need": "lgp", "t_no_paid": "lgn", "t_no_love": "gnp", "t_no_good": "lnp"}
VENN_TOUR = ["love", "good", "need", "paid", "passion", "mission", "vocation", "profession",
             "t_no_paid", "t_no_good", "t_no_love", "t_no_need", "center"]
QNAME = {"love": "Love", "good": "Good at", "need": "World needs", "paid": "Paid for"}


def _vregion(uid, key, sets, fill):
    letters = sets.split()
    x, y = VC[letters[-1]]
    inner = (f'<circle class="rg" data-sel="{key}" data-sets="{"".join(letters)}" cx="{x}" cy="{y}" r="{VR}" '
             f'style="fill:var(--v-{fill})"/>')
    for l in letters[:-1]:
        inner = f'<g clip-path="url(#{uid}-{l})">{inner}</g>'
    return inner


@slide_type("venn", ["circles"])
def r_venn(s, ctx):
    uid = f"v{ctx['idx']}"
    circ, ov, lens_notes, center = s["circles"], s.get("overlaps", {}), s.get("lenses", {}), s.get("center", {})
    defs = "".join(f'<clipPath id="{uid}-{l}"><circle cx="{x}" cy="{y}" r="{VR}"/></clipPath>' for l, (x, y) in VC.items())
    singles = "".join(
        f'<g class="bc" style="--d:{i * .22:.2f}s">{_vregion(uid, k, QUAD[k], k)}</g>' for i, k in enumerate(QUAD))
    pairs = "".join(_vregion(uid, k, v[0], k) for k, v in PAIRS.items())
    lenses = "".join(_vregion(uid, k, v[0], LENS_FILL[k]) for k, v in LENSES.items())
    quad = _vregion(uid, "center", "L G N P", "center")
    outlines = "".join(f'<circle cx="{x}" cy="{y}" r="{VR}"/>' for x, y in VC.values())
    # labels
    lab = ""
    pos = {"love": (0, -212), "good": (-205, -10), "need": (205, -10), "paid": (0, 192)}
    for k, (x, y) in pos.items():
        c = circ.get(k, {})
        a, b = c.get("label_top", QUAD_DEFAULT[k][0]), c.get("label", QUAD_DEFAULT[k][1])
        lab += f'<text x="{x}" y="{y}" class="vl1">{esc(a)}</text><text x="{x}" y="{y + 21}" class="vl2">{esc(b)}</text>'
    for k, (_, name, (x, y)) in PAIRS.items():
        lab += f'<text x="{x}" y="{y + 5}" class="vlp">{esc(ov.get(k, {}).get("label", name))}</text>'
    lab += f'<text x="0" y="8" class="vlc">{esc(center.get("label", "Ikigai"))}</text>'
    # callouts
    calls = ""
    for k, (_, feel, _m, (ax, ay), (tx, ty), d) in LENSES.items():
        lines = wrap(feel, 16)
        anchor = "end" if tx < 0 else "start"
        y0 = ty - (len(lines) - 1) * 10
        ts = "".join(f'<tspan x="{tx}" y="{y0 + j * 20}">{esc(t)}</tspan>' for j, t in enumerate(lines))
        bx = tx + (8 if tx < 0 else -8)
        calls += (f'<g class="callout"><path d="{d}" class="cl-path"/><circle cx="{ax}" cy="{ay}" r="5" class="cl-dot"/>'
                  f'<line x1="{bx}" x2="{bx}" y1="{y0 - 15}" y2="{y0 + (len(lines) - 1) * 20 + 6}" class="cl-bar"/>'
                  f'<text class="cl-t {anchor}">{ts}</text>'
                  f'<circle r="3.5" class="cl-pk"><animateMotion dur="3.2s" repeatCount="indefinite" path="{d}"/></circle></g>')
    svg = (f'<svg class="venn" viewBox="-420 -290 840 580" data-vb="-420 -290 840 580" data-vbn="-290 -290 580 580" '
           f'data-tour=\'{json.dumps(VENN_TOUR)}\' role="img" aria-label="Ikigai diagram"><defs>{defs}</defs>'
           f'{singles}<g class="bc" style="--d:.95s">{pairs}</g><g class="bc" style="--d:1.25s">{lenses}</g>'
           f'<g class="bc vcenter" style="--d:1.55s">{quad}</g>'
           f'<g class="bc voutline" style="--d:.8s">{outlines}</g><g class="bc vlabels" style="--d:1.75s">{lab}</g>'
           f'<g class="bc vcalls" style="--d:2.1s">{calls}</g></svg>')
    # panel templates
    tpl = '<template data-sel="intro"><p class="kicker">How to read this</p><h3>Four circles, one centre</h3>' \
          f'<p>{md(s.get("how", "Each circle is one question. Where two overlap you get a passion, mission, profession or vocation; where three overlap, the classic warning about the missing fourth. The centre, where all four meet, is Ikigai. Click any region, or let the tour play."))}</p></template>'
    for k in QUAD:
        c = circ.get(k, {})
        chips = "".join(f'<span class="chip">{md(i)}</span>' for i in c.get("items", []))
        tpl += (f'<template data-sel="{k}"><p class="kicker"><i class="sw" style="background:var(--v-{k})"></i>Circle · {QNAME[k]}</p>'
                f'<h3>{md(c.get("title", " ".join(QUAD_DEFAULT[k]).title()))}</h3>'
                f'{opt("<blockquote>{}</blockquote>", c.get("question"))}'
                f'<div class="chips">{chips}</div>{opt("<p class=summ>{}</p>", c.get("summary"))}</template>')
    for k, (sets, name, _) in PAIRS.items():
        o = ov.get(k, {})
        combo = " + ".join(QNAME[q] for q, l in QUAD.items() if l in sets.split())
        rows = ""
        for lab_, key in (("My expression", "expression"), ("Pitfall", "pitfall"), ("Correction", "correction")):
            if o.get(key):
                rows += f'<div class="vrow {key}"><b>{lab_}</b><span>{md(o[key])}</span></div>'
        tpl += (f'<template data-sel="{k}"><p class="kicker"><i class="sw" style="background:var(--v-{k})"></i>Overlap · {combo}</p>'
                f'<h3>{esc(o.get("label", name).title())}</h3>{rows}</template>')
    for k, (sets, feel, miss, *_r) in LENSES.items():
        note = lens_notes.get(k)
        tpl += (f'<template data-sel="{k}"><p class="kicker"><i class="sw" style="background:var(--v-{LENS_FILL[k]})"></i>Three circles · missing {QNAME[miss]}</p>'
                f'<h3>“{esc(feel)}”</h3><p>Everything is present except <b>{QNAME[miss].lower()}</b>. This is the classic way a near-Ikigai feels from the inside.</p>'
                f'{f"<div class=vrow><b>For me</b><span>{md(note)}</span></div>" if note else ""}</template>')
    tpl += (f'<template data-sel="center"><p class="kicker"><i class="sw" style="background:var(--v-center)"></i>All four · Ikigai</p>'
            f'<h3>{md(center.get("title", "My Ikigai"))}</h3><p class="big-s">{md(center.get("statement", ""))}</p>'
            f'{opt("<p class=summ>{}</p>", center.get("sub"))}</template>')
    chips = "".join(
        f'<button class="vchip" type="button" data-sel="{k}" style="--c:var(--v-{f})">{n}</button>' for k, n, f in [
            ("love", "Love", "love"), ("good", "Good at", "good"), ("need", "Needs", "need"), ("paid", "Paid", "paid"),
            ("passion", "Passion", "passion"), ("mission", "Mission", "mission"), ("profession", "Profession", "profession"),
            ("vocation", "Vocation", "vocation"), ("center", "Ikigai", "center")])
    return header(s) + f"""<div class="vgrid"><div class="vfig">{svg}<div class="vchips">{chips}{tour_btn()}</div></div>
<aside class="panel selpanel" aria-live="polite"></aside>{tpl}</div>""" + footer(s)


# ---- petals (six-dimension Ikigai) -------------------------------------------------------------------

@slide_type("petals", ["dims"])
def r_petals(s, ctx):
    dims = s["dims"]
    n = len(dims)
    petals, labels, tpl = "", "", ""
    radar = all("score" in d for d in dims)
    for i, d in enumerate(dims):
        a = -90 + i * 360 / n
        c = col(d.get("color"), i)
        petals += (f'<g transform="rotate({a + 90:.1f})"><path class="petal" data-sel="{i}" style="--c:{c};--d:{.25 + i * .18:.2f}s" '
                   f'd="M0,0 C46,-52 46,-132 0,-182 C-46,-132 -46,-52 0,0Z"/></g>')
        ix, iy = 112 * math.cos(math.radians(a)), 112 * math.sin(math.radians(a))
        lx, ly = 212 * math.cos(math.radians(a)), 212 * math.sin(math.radians(a))
        anchor = "middle" if abs(lx) < 40 else ("start" if lx > 0 else "end")
        labels += (f'<text x="{ix:.1f}" y="{iy + 9:.1f}" class="pi">{esc(d.get("icon", ""))}</text>'
                   f'<text x="{lx:.1f}" y="{ly + 5:.1f}" class="pn {anchor}" data-sel="{i}">{esc(d["name"])}</text>')
        tpl += (f'<template data-sel="{i}"><p class="kicker"><i class="sw" style="background:{c}"></i>Dimension {i + 1} of {n}</p>'
                f'<h3>{esc(d.get("icon", ""))} {md(d["name"])}</h3>'
                f'{opt("<blockquote>{}</blockquote>", d.get("question"))}'
                f'<p>{md(d.get("expression", ""))}</p>{opt("<p class=summ>Score: <b>{}</b> / 10</p>", d.get("score"), raw=True) if radar else ""}</template>')
    poly = ""
    if radar:
        pts = " ".join(f'{18.2 * d["score"] * math.cos(math.radians(-90 + i * 360 / n)):.1f},{18.2 * d["score"] * math.sin(math.radians(-90 + i * 360 / n)):.1f}' for i, d in enumerate(dims))
        poly = f'<polygon class="radar" points="{pts}"/>'
    center = s.get("center", "")
    svg = (f'<svg class="petals" viewBox="-290 -250 580 500" role="img" aria-label="Dimensions">{petals}{poly}'
           f'<circle r="34" class="pc"/><text y="5" class="pct">{esc(center)}</text>{labels}</svg>')
    tpl = f'<template data-sel="intro"><p class="kicker">How to read this</p><p>{md(s.get("how", "Each petal is one dimension of a whole life. Click a petal, or let them light up in turn."))}</p></template>' + tpl
    return header(s) + f'<div class="two sel-root"><div class="pfig">{svg}<div class="ctl">{tour_btn()}</div></div><aside class="panel selpanel"></aside>{tpl}</div>' + footer(s)


# ---- triad -----------------------------------------------------------------------------------------

@slide_type("triad", ["nodes"])
def r_triad(s, ctx):
    nodes = s["nodes"]
    P = [(200, 46), (52, 300), (348, 300)]
    lines = ""
    for a, b in ((0, 1), (1, 2), (2, 0)):
        (x1, y1), (x2, y2) = P[a], P[b]
        d = f"M{x1},{y1} L{x2},{y2}"
        lines += (f'<path d="{d}" class="tl"/><circle r="4" class="tpk"><animateMotion dur="{2.6 + a * .4:.1f}s" repeatCount="indefinite" path="{d}"/></circle>')
    html_nodes, cards = "", ""
    for i, (nd, (x, y)) in enumerate(zip(nodes, P)):
        c = col(nd.get("color"), i)
        html_nodes += (f'<button type="button" class="tnode" data-sel="{i}" style="left:{x / 4:.2f}%;top:{y / 3.6:.2f}%;--c:{c}">'
                       f'<span class="tn-i">{esc(nd.get("icon", ""))}</span><span class="tn-n">{md(nd["name"])}</span></button>')
        cards += (f'<article class="card tcard f" data-sel="{i}" style="--c:{c}"><div class="card-h"><span class="ci">{esc(nd.get("icon", ""))}</span>'
                  f'<h3>{md(nd["name"])}</h3>{opt("<span class=tag>{}</span>", nd.get("tag"))}</div><p>{md(nd.get("body", ""))}</p></article>')
    c = s.get("center", {})
    fig = (f'<div class="triad"><svg viewBox="0 0 400 360" aria-hidden="true"><circle cx="200" cy="215" r="168" class="tring"/>{lines}</svg>'
           f'{html_nodes}<div class="tcenter"><b>{md(c.get("title", ""))}</b><span>{md(c.get("body", ""))}</span></div></div>')
    return header(s) + f'<div class="two tgrid"><div>{fig}<div class="ctl">{tour_btn()}</div></div><div class="tcards">{cards}</div></div>' + footer(s)


# ---- wheel (Pancakrtya) ----------------------------------------------------------------------------

def _seg(r0, r1, a0, a1):
    def p(r, a):
        return r * math.cos(math.radians(a)), r * math.sin(math.radians(a))
    lg = 1 if a1 - a0 > 180 else 0
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = p(r1, a0), p(r1, a1), p(r0, a1), p(r0, a0)
    return f"M{x1:.1f},{y1:.1f} A{r1},{r1} 0 {lg} 1 {x2:.1f},{y2:.1f} L{x3:.1f},{y3:.1f} A{r0},{r0} 0 {lg} 0 {x4:.1f},{y4:.1f}Z"


@slide_type("wheel", ["segments"])
def r_wheel(s, ctx):
    segs = s["segments"]
    n = len(segs)
    step = 360 / n
    r0, r1 = 84, 196
    g, tpl = "", ""
    for i, sg in enumerate(segs):
        a0 = -90 - step / 2 + i * step + 1.2
        a1 = a0 + step - 2.4
        mid = math.radians((a0 + a1) / 2)
        c = col(sg.get("color"), i)
        rm = (r0 + r1) / 2
        x, y = rm * math.cos(mid), rm * math.sin(mid)
        g += (f'<g class="seg" data-sel="{i}" data-name="{esc(plain(sg["name"]))}" style="--c:{c};--tx:{12 * math.cos(mid):.1f}px;--ty:{12 * math.sin(mid):.1f}px">'
              f'<path d="{_seg(r0, r1, a0, a1)}"/><text x="{x:.1f}" y="{y - 6:.1f}" class="wi">{esc(sg.get("icon", ""))}</text>'
              f'<text x="{x:.1f}" y="{y + 20:.1f}" class="wn">{esc(sg["name"])}</text>' +
              (f'<text x="{x:.1f}" y="{y + 36:.1f}" class="ws">{esc(sg["sub"])}</text>' if sg.get("sub") else "") + '</g>')
        rows = "".join(f'<div class="vrow"><b>{md(k)}</b><span>{md(v)}</span></div>' for k, v in (sg.get("rows") or {}).items())
        tpl += (f'<template data-sel="{i}"><p class="kicker"><i class="sw" style="background:{c}"></i>{i + 1} of {n}{opt(" · {}", esc(sg.get("sub", "")), raw=True)}</p>'
                f'<h3>{esc(sg.get("icon", ""))} {md(sg["name"])}</h3>{opt("<p>{}</p>", sg.get("body"))}{rows}</template>')
    ring = "".join(f'<circle cx="{214 * math.cos(math.radians(k * 7.5)):.1f}" cy="{214 * math.sin(math.radians(k * 7.5)):.1f}" r="2"/>' for k in range(48))
    ct = s.get("center", "")
    svg = (f'<svg class="wheel" viewBox="-230 -230 460 460" role="img" aria-label="Wheel"><g class="wring">{ring}</g>{g}'
           f'<circle r="76" class="wc"/><text y="-8" class="wct">{esc(ct)}</text><text y="18" class="wcname"></text></svg>')
    tpl = f'<template data-sel="intro"><p class="kicker">How to read this</p><p>{md(s.get("how", "Each segment is one function. Click one, or let the wheel turn."))}</p></template>' + tpl
    return header(s) + f'<div class="two sel-root"><div class="wfig">{svg}<div class="ctl">{tour_btn()}</div></div><aside class="panel selpanel"></aside>{tpl}</div>' + footer(s)


# ---- trinity (three overlapping circles inside a sustaining ring) ------------------------------------

@slide_type("trinity", ["circles"])
def r_trinity(s, ctx):
    cs = s["circles"][:3]
    g, tpl = "", ""
    for i, c in enumerate(cs):
        a = math.radians(-90 + i * 120)
        x, y = 72 * math.cos(a), 72 * math.sin(a)
        lx, ly = 112 * math.cos(a), 112 * math.sin(a)
        cc = col(c.get("color"), i)
        g += (f'<circle class="tc" data-sel="{i}" cx="{x:.1f}" cy="{y:.1f}" r="108" style="--c:{cc};--d:{.2 + i * .25:.2f}s"/>')
        tpl += (f'<template data-sel="{i}"><p class="kicker"><i class="sw" style="background:{cc}"></i>{esc(c.get("icon", ""))} {esc(c["name"])}</p>'
                f'<h3>{md(c.get("aspiration", ""))}</h3>{opt("<blockquote>{}</blockquote>", c.get("question"))}</template>')
        g += f'<text x="{lx:.1f}" y="{ly - 4:.1f}" class="tci">{esc(c.get("icon", ""))}</text><text x="{lx:.1f}" y="{ly + 18:.1f}" class="tcn">{esc(c["name"])}</text>'
    outer = s.get("outer", {})
    ring_txt = esc(" · ".join([outer.get("name", "")] + outer.get("words", [])) + " · ") * 3
    tpl += (f'<template data-sel="outer"><p class="kicker">The ring around everything</p><h3>{esc(outer.get("icon", ""))} {md(outer.get("name", ""))}</h3>'
            f'<blockquote>{md(outer.get("question", ""))}</blockquote><p>{md(outer.get("body", ""))}</p></template>')
    uid = f"tr{ctx['idx']}"
    svg = (f'<svg class="trinity" viewBox="-260 -260 520 520" role="img" aria-label="Three aspirations"><defs><path id="{uid}" d="M0,-232 A232,232 0 1 1 -0.1,-232"/></defs>'
           f'<g class="tring2" data-sel="outer"><circle r="232" class="tro"/><text class="trt"><textPath href="#{uid}">{ring_txt}</textPath></text></g>'
           f'{g}<text y="6" class="tct">{esc(s.get("center", ""))}</text></svg>')
    tpl = f'<template data-sel="intro"><p class="kicker">How to read this</p><p>{md(s.get("how", "Three aspirations overlap at the centre; the ring around them is what keeps the whole life possible. Click any of them."))}</p></template>' + tpl
    return header(s) + f'<div class="two sel-root"><div class="trfig">{svg}<div class="ctl">{tour_btn()}</div></div><aside class="panel selpanel"></aside>{tpl}</div>' + footer(s)


# ---- vision / mission cascade ------------------------------------------------------------------------

@slide_type("vmv", ["vision", "mission"])
def r_vmv(s, ctx):
    pil = "".join(
        f'<div class="pill f" style="--c:{col(p.get("color"), i)}"><span>{esc(p.get("icon", ""))}</span><b>{md(p["title"])}</b><small>{md(p.get("body", ""))}</small></div>'
        for i, p in enumerate(s.get("pillars", [])))
    vals = "".join(f'<span class="val" title="{esc(v.get("desc", ""))}"><b>{md(v["name"])}</b>{opt("<small>{}</small>", v.get("desc"))}</span>' for v in s.get("values", []))
    idt = s.get("identity")
    lab = s.get("labels", {})
    out = header(s) + '<div class="vmv"><div class="beam"><i></i></div><div class="star">✦</div>'
    out += f'<div class="vm vision f"><span class="lbl">{esc(lab.get("vision", "Vision · the world I am working toward"))}</span><p>{md(s["vision"])}</p></div>'
    out += f'<div class="vm mission f"><span class="lbl">{esc(lab.get("mission", "Mission · what I do about it"))}</span><p>{md(s["mission"])}</p></div>'
    if pil:
        out += f'<span class="lbl f">{esc(lab.get("pillars", "How · strategic pillars"))}</span><div class="pills">{pil}</div>'
    if vals:
        out += f'<span class="lbl f">{esc(lab.get("values", "Values · how I behave on the way"))}</span><div class="vals f">{vals}</div>'
    if idt:
        out += f'<div class="vm identity f"><span class="lbl">{esc(lab.get("identity", "Identity · who I am becoming"))}</span><p><b>{md(idt.get("title", ""))}</b> {md(idt.get("body", ""))}</p></div>'
    return out + "</div>" + footer(s)


# ---- ecosystem ------------------------------------------------------------------------------------------

@slide_type("ecosystem", ["hub", "nodes"])
def r_ecosystem(s, ctx):
    hub, nodes, flows = s["hub"], s["nodes"], s.get("flows", [])
    W_, H_, cx, cy, rx, ry = 1000, 640, 500, 320, 390, 232
    pos = {"hub": (cx, cy)}
    n = len(nodes)
    for i, nd in enumerate(nodes):
        a = math.radians(-90 + i * 360 / n)
        pos[nd["id"]] = (cx + rx * math.cos(a), cy + ry * math.sin(a))
    uid = f"e{ctx['idx']}"
    paths = ""
    names = {"hub": plain(hub.get("title", ""))} | {nd["id"]: plain(nd["title"]) for nd in nodes}
    pairs = {(f["from"], f["to"]) for f in flows}

    def trim(xa, ya, xb, yb, t):  # move a point t units toward (xb, yb) so arrows stop at the node edge
        d = math.hypot(xb - xa, yb - ya) or 1
        return xa + (xb - xa) * t / d, ya + (yb - ya) * t / d

    for f in flows:
        (x1, y1), (x2, y2) = pos[f["from"]], pos[f["to"]]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        L = math.hypot(x2 - x1, y2 - y1) or 1
        nx, ny = -(y2 - y1) / L, (x2 - x1) / L
        bend = 0 if "hub" in (f["from"], f["to"]) else 0.22      # node<->node flows bow toward the hub
        side = 22 if (f["to"], f["from"]) in pairs else 0         # opposite-direction twins split apart
        qx, qy = mx + (cx - mx) * bend + nx * side, my + (cy - my) * bend + ny * side
        sx, sy = trim(x1, y1, qx, qy, 70 if f["from"] == "hub" else 52)
        ex, ey = trim(x2, y2, qx, qy, 78 if f["to"] == "hub" else 58)
        cap = f'<b>{esc(names[f["from"]])} → {esc(names[f["to"]])}</b> · {esc(f.get("label", ""))}'
        paths += (f'<g class="fl" data-from="{esc(f["from"])}" data-to="{esc(f["to"])}" data-cap="{esc(cap)}">'
                  f'<path d="M{sx:.0f},{sy:.0f} Q{qx:.0f},{qy:.0f} {ex:.0f},{ey:.0f}" marker-end="url(#{uid}-a)"/></g>')
    svg = (f'<svg class="eco" viewBox="0 0 {W_} {H_}" aria-hidden="true"><defs><marker id="{uid}-a" viewBox="0 0 10 10" refX="8" refY="5" '
           f'markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10z" class="ah"/></marker></defs>'
           f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" class="eorbit"/>{paths}</svg>')
    hx, hy = pos["hub"]
    nodes_html = (f'<div class="enode hub" data-id="hub" style="left:{hx / W_ * 100:.2f}%;top:{hy / H_ * 100:.2f}%">'
                  f'<span class="ei">{esc(hub.get("icon", ""))}</span><b>{md(hub["title"])}</b><small>{md(hub.get("body", ""))}</small></div>')
    lst_html = f'<div class="eitem hub"><span class="ei">{esc(hub.get("icon", ""))}</span><div><b>{md(hub["title"])}</b><small>{md(hub.get("body", ""))}</small></div></div>'
    for i, nd in enumerate(nodes):
        x, y = pos[nd["id"]]
        c = col(nd.get("color"), i)
        nodes_html += (f'<div class="enode" data-id="{esc(nd["id"])}" style="left:{x / W_ * 100:.2f}%;top:{y / H_ * 100:.2f}%;--c:{c}">'
                       f'<span class="ei">{esc(nd.get("icon", ""))}</span><b>{md(nd["title"])}</b><small>{md(nd.get("body", ""))}</small></div>')
        lst_html += f'<div class="eitem" style="--c:{c}"><span class="ei">{esc(nd.get("icon", ""))}</span><div><b>{md(nd["title"])}</b><small>{md(nd.get("body", ""))}</small></div></div>'
    flow_list = "".join(f'<li><b>{esc(names[f["from"]])} → {esc(names[f["to"]])}</b>: {md(f.get("label", ""))}</li>' for f in flows)
    outs = "".join(f'<span class="chip">{md(o)}</span>' for o in s.get("outcomes", []))
    return header(s) + f"""<div class="ecowrap f"><div class="ecofig">{svg}{nodes_html}</div>
<p class="ecap" aria-live="polite">Watch what circulates between the parts…</p></div>
<div class="elist">{lst_html}<ul class="dots">{flow_list}</ul></div>
{f'<div class="chips outs f"><span class="lbl">What flows out</span>{outs}</div>' if outs else ''}""" + footer(s)


# ---- cycle -----------------------------------------------------------------------------------------------

@slide_type("cycle", ["steps"])
def r_cycle(s, ctx):
    steps = s["steps"]
    n = len(steps)
    nodes, tpl, lst_ = "", "", ""
    for i, st in enumerate(steps):
        a = math.radians(-90 + i * 360 / n)
        x, y = 50 + 42 * math.cos(a), 50 + 42 * math.sin(a)
        c = col(st.get("color"), i)
        nodes += (f'<div class="cstep" data-i="{i}" style="left:{x:.2f}%;top:{y:.2f}%;--c:{c}"><span class="cn">{i + 1}</span>'
                  f'<span class="cic">{esc(st.get("icon", ""))}</span><b>{md(st["title"])}</b></div>')
        tpl += (f'<template data-i="{i}"><span class="kicker">Step {i + 1} of {n}</span><b class="ct">{esc(st.get("icon", ""))} {md(st["title"])}</b>'
                f'<span class="cb">{md(st.get("body", ""))}</span></template>')
        lst_ += f'<li style="--c:{c}"><b>{i + 1}. {esc(st.get("icon", ""))} {md(st["title"])}</b> {md(st.get("body", ""))}</li>'
    center = s.get("center", "")
    return header(s) + f"""<div class="cycle f" data-period="{s.get("period", n * 2600)}"><svg viewBox="0 0 100 100" aria-hidden="true">
<circle cx="50" cy="50" r="42" class="cring"/></svg>{nodes}<div class="cdot"></div>
<div class="ccenter"><div class="cbody">{md(center)}</div></div>{tpl}</div>
<ol class="clist">{lst_}</ol>{f'<p class="center-note f">{md(center)}</p>' if center else ''}""" + footer(s)


# ---- chain ------------------------------------------------------------------------------------------------

@slide_type("chain", ["nodes"])
def r_chain(s, ctx):
    out = header(s) + '<div class="chain">'
    for i, nd in enumerate(s["nodes"]):
        c = col(nd.get("color"), i)
        if i:
            out += f'<div class="carrow f"><i></i>{opt("<small>{}</small>", nd.get("via"))}</div>'
        out += (f'<div class="cnode f" style="--c:{c}">{opt("<span class=sub>{}</span>", nd.get("sub"))}'
                f'<span class="ci">{esc(nd.get("icon", ""))}</span><b>{md(nd["title"])}</b><small>{md(nd.get("body", ""))}</small></div>')
    return out + "</div>" + footer(s)


# ---- layers ------------------------------------------------------------------------------------------------

@slide_type("layers", ["layers"])
def r_layers(s, ctx):
    ls = s["layers"]
    n = len(ls)
    rows = ""
    for i, l in enumerate(ls):
        c = col(l.get("color"), i)
        chips = "".join(f'<span class="chip">{md(x)}</span>' for x in l.get("items", []))
        rows += (f'<div class="layer" style="--c:{c};--d:{(n - 1 - i) * .35 + .2:.2f}s"><div class="lh"><span class="ci">{esc(l.get("icon", ""))}</span>'
                 f'<div><b>{md(l["title"])}</b>{opt("<small>{}</small>", l.get("purpose"))}</div></div>'
                 f'<div class="lb">{opt("<p>{}</p>", l.get("body"))}<div class="chips">{chips}</div></div></div>')
    side = s.get("arrow")
    arrow = ""
    if side:
        arrow = f'<div class="larrow {esc(side.get("direction", "up"))}"><i></i><i></i><i></i><span>{md(side.get("label", ""))}</span></div>'
    return header(s) + f'<div class="layers{" has-arrow" if arrow else ""}"><div class="lstack">{rows}</div>{arrow}</div>' + footer(s)


# ---- roadmap ------------------------------------------------------------------------------------------------

@slide_type("roadmap", ["phases"])
def r_roadmap(s, ctx):
    ph = s["phases"]
    now = s.get("now")
    cols = ""
    for i, p in enumerate(ph):
        c = col(p.get("color"), i)
        pin = '<span class="pin">● You are here</span>' if now == i else ""
        cols += (f'<div class="rph" style="--c:{c}"><div class="rnode">{pin}<span class="rdot">{esc(p.get("icon", "")) or i + 1}</span></div>'
                 f'<div class="rcard"><span class="rwhen">{md(p.get("when", ""))}</span><b>{md(p["title"])}</b>'
                 f'{opt("<p class=rgoal>{}</p>", p.get("goal"))}{lst(p.get("items"), "dots")}</div></div>')
    return header(s) + f'<div class="rm" style="--n:{len(ph)}"><div class="rtrack"><i class="rfill"></i><i class="rcomet"></i></div>{cols}</div>' + footer(s)


# ---- scores -------------------------------------------------------------------------------------------------

@slide_type("scores", ["criteria", "items"])
def r_scores(s, ctx):
    cr, items = s["criteria"], s["items"]
    mx = s.get("max", 10)
    tot_max = mx * len(cr)
    top = s.get("top", 3)
    ranked = sorted(enumerate(items), key=lambda t: (-sum(t[1]["scores"]), t[0]))
    th = '<th>#</th><th data-sort="name">Idea</th>' + "".join(
        f'<th data-sort="{j}" title="{esc(c.get("desc", ""))}"><span>{esc(c.get("icon", ""))}</span>{esc(c["name"])}</th>' for j, c in enumerate(cr)
    ) + '<th data-sort="t">Total</th>'
    rows = ""
    for r, (i, it) in enumerate(ranked):
        tot = sum(it["scores"])
        cells = "".join(f'<td class="heat" style="--a:{max(5, round((v - mx / 2) / (mx / 2) * 55))}%">{v}</td>' for v in it["scores"])
        data = " ".join(f'data-s{j}="{v}"' for j, v in enumerate(it["scores"]))
        rows += (f'<tr class="{"top" if r < top else ""}" {data} data-st="{tot}" data-r="{r}"><td class="rk">{r + 1}</td>'
                 f'<td class="nm">{md(it["name"])}{opt("<small>{}</small>", it.get("note"))}</td>{cells}'
                 f'<td class="tot"><div class="totw"><div class="sbar"><i data-w="{tot / tot_max * 100:.1f}%"></i></div><b data-count="{tot}">{tot}</b><small>/{tot_max}</small></div></td></tr>')
    return header(s) + f'<div class="tscroll f"><table class="t scores"><thead><tr>{th}</tr></thead><tbody>{rows}</tbody></table></div><p class="note">Click a column header to re-rank by that criterion.</p>' + footer(s)


# ---- compare ------------------------------------------------------------------------------------------------

@slide_type("compare", ["columns"])
def r_compare(s, ctx):
    out = header(s) + '<div class="compare">'
    for i, c in enumerate(s["columns"]):
        cc = col(c.get("color"), i)
        rec = '<span class="rec">★ Recommended</span>' if c.get("recommended") else ""
        body = f'<p>{md(c["body"])}</p>' if c.get("body") else ""
        pts = lst(c.get("points"), "dots")
        pc = ""
        if c.get("pros"):
            pc += f'<div class="pc pro"><b>Greatest attraction</b>{md(c["pros"])}</div>'
        if c.get("cons"):
            pc += f'<div class="pc con"><b>Greatest challenge</b>{md(c["cons"])}</div>'
        out += (f'<article class="ccol f{" recd" if c.get("recommended") else ""}" style="--c:{cc}">{rec}'
                f'{opt("<span class=tag>{}</span>", c.get("tag"))}'
                f'<h3><span class="ci">{esc(c.get("icon", ""))}</span>{md(c["title"])}</h3>{body}{pts}{pc}</article>')
    out += "</div>"
    if s.get("question"):
        out += f'<p class="big-q f">{md(s["question"])}</p>'
    return out + footer(s)


@slide_type("questions", ["prompts"])
def r_questions(s, ctx):
    out = header(s) + '<ol class="qs">'
    for i, q in enumerate(s["prompts"]):
        out += f'<li class="f" style="--c:{col(q.get("color"), i)}"><span class="qn">{i + 1}</span><div><p class="qq">{md(q["q"])}</p>{opt("<p class=qh>{}</p>", q.get("hint"))}</div></li>'
    return out + "</ol>" + footer(s)


@slide_type("image", ["src"])
def r_image(s, ctx):
    p = (ctx["base"] / s["src"]).resolve()
    if p.exists():
        mime = mimetypes.guess_type(str(p))[0] or ("image/webp" if p.suffix == ".webp" else "image/png")
        src = f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()
    else:
        src = esc(s["src"])
    cap = f'<figcaption>{md(s.get("caption", ""))}{opt(" · <i>{}</i>", s.get("credit"))}</figcaption>'
    fig = f'<figure class="img f"><img src="{src}" alt="{esc(s.get("alt", s.get("caption", "")))}">{cap}</figure>'
    side = ""
    if s.get("bullets") or s.get("paras"):
        side = "".join(f'<p class="para f">{md(p_)}</p>' for p_ in s.get("paras", [])) + f'<div class="f">{lst(s.get("bullets"))}</div>'
        return header(s) + f'<div class="two">{fig}<div>{side}</div></div>' + footer(s)
    return header(s) + fig + footer(s)


@slide_type("closing", ["words"])
def r_closing(s, ctx):
    words = "".join(f'<span class="cw f" style="--c:{col(None, i)}">{md(w)}</span>' for i, w in enumerate(s["words"]))
    lines = "".join(f'<p class="f">{md(l)}</p>' for l in s.get("lines", []))
    return f"""<div class="closing"><div class="hero-art bg">{mandala()}</div>
{f'<p class="kicker f">{md(s["kicker"])}</p>' if s.get("kicker") else ''}{f'<h2 class="ctitle f">{md(s["title"])}</h2>' if s.get("title") else ''}
<div class="cwords">{words}</div><div class="clines">{lines}</div>
{f'<p class="final f">{md(s["final"])}</p>' if s.get("final") else ''}</div>"""


# --------------------------------------------------------------------------------------------- assemble

CSS = r"""
:root{--bg:#FBF7EE;--bg2:#F3ECDD;--panel:#FFFFFF;--ink:#1E2A22;--muted:#68715F;--line:#E6DDCB;--acc:#3F7D5A;--acc2:#C2547A;
--love:#E9B930;--good:#8DB43F;--need:#E07D67;--paid:#2FB38C;--lotus:#C2547A;--indigo:#4B55A8;--gold:#C2902A;--warn:#B45309;--bad:#B42318;--ok:#2F7D4A;
--v-love:#FCE38A;--v-good:#E2F0A0;--v-need:#F4B6A8;--v-paid:#B8F0DD;--v-passion:#D6E37C;--v-mission:#F6C68A;--v-profession:#BFE9B4;--v-vocation:#D9CCB5;
--v-lgn:#CDBE86;--v-lgp:#A9C08A;--v-lnp:#CFA98A;--v-gnp:#A7BF95;--v-center:#5D7A4C;--v-center-ink:#FFFFFF;--v-stroke:#FFFFFF;--v-ink:#1E2A22;
--star:#C9A44A;--shadow:0 10px 30px rgba(70,55,20,.08);--chip:#F1EAD9;--hl:rgba(63,125,90,.12)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0C1210;--bg2:#111915;--panel:#151F1A;--ink:#EEE9DC;--muted:#A5AE9E;--line:#26332B;--acc:#7FD1A1;--acc2:#F28BB0;
--love:#F2CE58;--good:#B5D86A;--need:#F29B86;--paid:#5ED6B1;--lotus:#F28BB0;--indigo:#9AA3F2;--gold:#E8C062;--warn:#FBBF24;--bad:#F87171;--ok:#6EE7A0;
--v-love:#6E5B1C;--v-good:#4E5C22;--v-need:#6E3A31;--v-paid:#1D5C4A;--v-passion:#6A6E24;--v-mission:#7E5728;--v-profession:#33633B;--v-vocation:#5E5241;
--v-lgn:#857740;--v-lgp:#5C7A3D;--v-lnp:#875D44;--v-gnp:#4D7253;--v-center:#B8DB8C;--v-center-ink:#10200F;--v-stroke:#0C1210;--v-ink:#F3EFE3;
--star:#FFFFFF;--shadow:none;--chip:#1D2922;--hl:rgba(127,209,161,.12)}}
:root[data-theme="dark"]{--bg:#0C1210;--bg2:#111915;--panel:#151F1A;--ink:#EEE9DC;--muted:#A5AE9E;--line:#26332B;--acc:#7FD1A1;--acc2:#F28BB0;
--love:#F2CE58;--good:#B5D86A;--need:#F29B86;--paid:#5ED6B1;--lotus:#F28BB0;--indigo:#9AA3F2;--gold:#E8C062;--warn:#FBBF24;--bad:#F87171;--ok:#6EE7A0;
--v-love:#6E5B1C;--v-good:#4E5C22;--v-need:#6E3A31;--v-paid:#1D5C4A;--v-passion:#6A6E24;--v-mission:#7E5728;--v-profession:#33633B;--v-vocation:#5E5241;
--v-lgn:#857740;--v-lgp:#5C7A3D;--v-lnp:#875D44;--v-gnp:#4D7253;--v-center:#B8DB8C;--v-center-ink:#10200F;--v-stroke:#0C1210;--v-ink:#F3EFE3;
--star:#FFFFFF;--shadow:none;--chip:#1D2922;--hl:rgba(127,209,161,.12)}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);font:16px/1.55 Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;overflow:hidden}
.serif,h1,h2,.big-quote,.big-q,.cw,.ctitle,.vm p,.final{font-family:Fraunces,"Noto Serif",Georgia,serif}
#stars{position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:0}
#deck{position:fixed;inset:0;z-index:1}
.slide{position:absolute;inset:0;padding:54px max(16px,5vw) 84px;overflow-y:auto;overflow-x:hidden;opacity:0;visibility:hidden;transform:translateX(40px);
transition:opacity .5s ease,transform .5s ease,visibility .5s}
.slide.active{opacity:1;visibility:visible;transform:none}.slide.prev{transform:translateX(-40px)}
.slide{display:flex;flex-direction:column}.slide>.wrap{margin:auto;width:100%;max-width:1220px}
h1,h2,h3{line-height:1.18;margin:.15em 0 .45em;overflow-wrap:anywhere}
h2{font-size:clamp(24px,3.2vw,40px);font-weight:600;letter-spacing:-.01em}
h2 b,.title b{background:linear-gradient(90deg,var(--acc),var(--acc2));-webkit-background-clip:text;background-clip:text;color:transparent}
h3{font-size:18px;margin:.1em 0 .35em}
.kicker{text-transform:uppercase;letter-spacing:.14em;color:var(--acc);font-size:12.5px;font-weight:600;margin:0 0 4px}
.lead{font-size:clamp(16px,1.6vw,19px);color:var(--muted);max-width:900px;margin-top:0}
.note{color:var(--muted);font-size:13.5px;margin-top:14px}
blockquote{margin:14px 0;padding:12px 18px;border-left:4px solid var(--acc2);background:var(--panel);border-radius:8px;font-style:italic;box-shadow:var(--shadow)}
kbd{border:1px solid var(--line);border-bottom-width:2px;border-radius:4px;padding:0 5px;font-size:12px;background:var(--panel)}
code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.9em;background:var(--chip);padding:1px 5px;border-radius:4px}
.f{opacity:0;transform:translateY(14px);transition:opacity .55s ease,transform .55s cubic-bezier(.2,.8,.2,1)}.f.on{opacity:1;transform:none}
.two{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:26px;align-items:start}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px 20px;box-shadow:var(--shadow);min-height:220px}
.panel.swap{animation:swap .45s ease}@keyframes swap{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.panel h3{font-family:Fraunces,"Noto Serif",Georgia,serif;font-size:22px;font-weight:600}
.panel blockquote{box-shadow:none;background:var(--bg2)}
.sw{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:7px;vertical-align:-1px;border:1px solid var(--line)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
.chip{background:var(--chip);border:1px solid var(--line);border-radius:99px;padding:3px 11px;font-size:13.5px}
.summ{color:var(--muted);font-size:14.5px;border-top:1px dashed var(--line);padding-top:8px}
.big-s{font-family:Fraunces,"Noto Serif",Georgia,serif;font-size:19px;line-height:1.45}
.vrow{display:grid;grid-template-columns:118px 1fr;gap:10px;padding:8px 0;border-bottom:1px solid var(--line);font-size:14.5px}
.vrow:last-child{border-bottom:0}.vrow b{color:var(--muted);font-weight:600;font-size:12.5px;text-transform:uppercase;letter-spacing:.06em;padding-top:2px}
.vrow.pitfall span{color:var(--warn)}.vrow.correction span{color:var(--ok)}
.ctl{display:flex;justify-content:center;margin-top:6px}
button{font:inherit;color:inherit}
.seltour{background:var(--panel);border:1px solid var(--line);border-radius:99px;padding:5px 14px;font-size:13px;cursor:pointer}
.seltour:hover{border-color:var(--acc)}
ul.ticks,ul.dots{list-style:none;padding:0;margin:8px 0}
ul.ticks li{padding:5px 0 5px 26px;position:relative}ul.ticks li:before{content:"✦";position:absolute;left:4px;color:var(--acc2);font-size:13px;top:7px}
ul.dots li{padding:2px 0 2px 16px;position:relative;font-size:14px}ul.dots li:before{content:"";position:absolute;left:3px;top:11px;width:6px;height:6px;border-radius:50%;background:var(--c,var(--acc))}
/* hero */
.hero-wrap{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:30px;align-items:center;width:100%}
.title{font-size:clamp(38px,6.4vw,78px);font-weight:600;letter-spacing:-.02em;margin:.1em 0 .1em}
.jp{font-size:clamp(20px,2.6vw,30px);color:var(--acc2);margin:0;letter-spacing:.2em}
.sub{font-size:clamp(17px,2vw,23px);color:var(--muted);max-width:760px}
.tagline{font-family:Fraunces,"Noto Serif",Georgia,serif;font-size:clamp(19px,2.3vw,28px);border-left:4px solid var(--love);padding-left:16px;max-width:760px}
.hint{color:var(--muted);font-size:13px;margin-top:26px}
.hero-art svg{width:100%;max-width:520px;display:block;margin:auto;overflow:visible}
.mandala .m-ring{fill:none;stroke:var(--gold);stroke-width:1;stroke-dasharray:3 7;opacity:.6;transform-origin:center;animation:spin 140s linear infinite}
.mandala .m-dots{fill:var(--gold);opacity:.55;transform-origin:center;animation:spin 90s linear infinite reverse}
.mandala .m-petals{fill:none;stroke:var(--acc2);stroke-width:1.1;opacity:.45;transform-origin:center;animation:spin 70s linear infinite reverse}
.mandala .m-core{transform-origin:center;animation:spin 50s linear infinite}
.mandala .mc{opacity:.85;stroke:var(--v-stroke);stroke-width:2.5}
.mandala .m-center{fill:var(--v-center);transform-origin:center;transform-box:fill-box;animation:pulse 3.2s ease-in-out infinite}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes pulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.35);opacity:.8}}
/* agenda */
.agenda{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px;margin-top:10px}
.ag{display:grid;grid-template-columns:auto 1fr;grid-template-rows:auto auto;gap:2px 10px;text-align:left;background:var(--panel);border:1px solid var(--line);
border-left:5px solid var(--c);border-radius:12px;padding:12px 14px;cursor:pointer;box-shadow:var(--shadow);transition:transform .2s}
.ag:hover{transform:translateY(-3px)}.ag-n{grid-row:span 2;font-family:Fraunces,Georgia,serif;font-size:26px;color:var(--c);line-height:1}
.ag-i{display:none}.ag b{font-size:15.5px}.ag span:last-child{font-size:13px;color:var(--muted)}
/* statement */
.skt{font-family:"Noto Serif Devanagari","Noto Serif",serif;font-size:clamp(22px,3vw,34px);color:var(--acc2);margin:.2em 0}
.big-quote{font-size:clamp(24px,3.4vw,42px);line-height:1.3;max-width:1000px;margin:.3em 0 .6em;font-weight:500}
.big-quote b{color:var(--acc)}
.st-lines p{font-size:clamp(16px,1.7vw,20px);max-width:900px;margin:.45em 0;padding-left:18px;border-left:2px solid var(--line)}
.attr{color:var(--muted);font-style:italic}
.para{font-size:17px;max-width:920px}
/* cards */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,var(--min)),1fr));gap:12px;margin:8px 0}
.card{background:var(--panel);border:1px solid var(--line);border-top:4px solid var(--c);border-radius:12px;padding:12px 15px;box-shadow:var(--shadow);transition:transform .25s,box-shadow .25s}
.card:hover{transform:translateY(-3px)}
.card-h{display:flex;align-items:center;gap:6px 9px;flex-wrap:wrap}.card-h h3{margin:0;font-size:16px;flex:1 1 120px;min-width:0}
.ci{font-size:22px;line-height:1}.card p{margin:.4em 0 0;font-size:14.5px;color:var(--muted)}
.card .tag,.ccol .tag{font-size:11px;padding:2px 8px;border-radius:99px;background:var(--chip);border:1px solid var(--line);color:var(--muted)}
.remedy{color:var(--ok)!important;font-weight:500}
.cards.warn .card{border-top-color:var(--warn)}
/* tables */
.tscroll{overflow-x:auto;-webkit-overflow-scrolling:touch;border-radius:12px}
.t{border-collapse:collapse;width:100%;background:var(--panel);border-radius:12px;overflow:hidden;box-shadow:var(--shadow);font-size:14.5px}
.t th,.t td{padding:9px 11px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.t th{background:var(--chip);font-size:12px;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap}
.t.sm{font-size:13.5px}.t tr.hl td{background:var(--hl)}.t td:first-child{font-weight:600}
/* venn */
.vgrid{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(280px,1fr);gap:22px;align-items:start}
.venn{width:100%;height:auto;display:block;overflow:visible}
.venn .rg{cursor:pointer;transition:opacity .35s,filter .35s}
.venn.focus .rg{opacity:.28}.venn.focus .rg.on{opacity:1;filter:drop-shadow(0 0 10px rgba(255,220,120,.55))}
.venn .voutline circle{fill:none;stroke:var(--v-stroke);stroke-width:4;pointer-events:none}
.venn text{pointer-events:none;fill:var(--v-ink);text-anchor:middle;font-family:Inter,system-ui,sans-serif}
.venn .vl1{font-size:15px}.venn .vl2{font-size:17px;font-weight:800;letter-spacing:.02em}
.venn .vlp{font-size:14px;font-weight:800;letter-spacing:.06em}
.venn .vlc{font-family:Fraunces,Georgia,serif;font-size:27px;fill:var(--v-center-ink);font-weight:600}
.venn .cl-path{fill:none;stroke:var(--muted);stroke-width:2.2;stroke-dasharray:1 5;stroke-linecap:round}
.venn .cl-dot{fill:var(--muted);stroke:var(--v-stroke);stroke-width:2}.venn .cl-pk{fill:var(--acc2)}
.venn .cl-bar{stroke:var(--muted);stroke-width:4}.venn.narrow .vcalls{display:none}
.venn .cl-t{font-size:16px;fill:var(--ink);font-weight:500}.venn .cl-t.end,.petals text.end{text-anchor:end}.venn .cl-t.start,.petals text.start{text-anchor:start}
.bc{transform-box:fill-box;transform-origin:center}
.run .bc{animation:pop .9s cubic-bezier(.2,.8,.2,1) var(--d,0s) both}
@keyframes pop{from{opacity:0;transform:scale(.6)}to{opacity:1;transform:none}}
.run .vcenter .rg{animation:glow 3s ease-in-out 2.4s infinite}
@keyframes glow{0%,100%{filter:none}50%{filter:drop-shadow(0 0 14px rgba(160,220,120,.9))}}
.vchips{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:6px}
.vchip{border:1px solid var(--line);background:var(--panel);border-radius:99px;padding:3px 11px 3px 8px;font-size:12.5px;cursor:pointer}
.vchip:before{content:"";display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--c);margin-right:6px;vertical-align:-1px}
.vchip.on{border-color:var(--acc);box-shadow:0 0 0 2px var(--hl)}
/* petals */
.petals,.wheel,.trinity{width:100%;max-width:470px;display:block;margin:auto;overflow:visible}
.petal{fill:var(--c);opacity:.82;stroke:var(--v-stroke);stroke-width:2.5;cursor:pointer;transform-box:fill-box;transform-origin:50% 100%;transition:opacity .3s}
.run .petal{animation:bloom 1s cubic-bezier(.2,.8,.2,1) var(--d) both}
@keyframes bloom{from{transform:scale(0);opacity:0}to{transform:scale(1);opacity:.82}}
.sel-root.focus .petal{opacity:.35}.sel-root .petal.on{opacity:1!important;filter:drop-shadow(0 0 10px var(--c))}
.petals text{text-anchor:middle;fill:var(--ink)}.petals .pi{font-size:24px}.petals .pn{font-size:16px;font-weight:700;cursor:pointer}
.petals .pn.on{fill:var(--acc)}.petals .pc{fill:var(--v-center)}.petals .pct{fill:var(--v-center-ink);font-size:13px;font-weight:700}
.radar{fill:rgba(194,84,122,.18);stroke:var(--acc2);stroke-width:2.5}
/* triad */
.triad{position:relative;width:100%;max-width:520px;margin:auto;aspect-ratio:400/360}
.triad svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
.triad .tring{fill:none;stroke:var(--gold);stroke-dasharray:2 8;stroke-width:1.5;transform-origin:200px 215px;animation:spin 60s linear infinite;opacity:.7}
.triad .tl{stroke:var(--line);stroke-width:3;fill:none}.triad .tpk{fill:var(--acc2)}
.tnode{position:absolute;transform:translate(-50%,-50%);width:clamp(84px,22%,118px);aspect-ratio:1;border-radius:50%;background:var(--panel);
border:3px solid var(--c);display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;box-shadow:var(--shadow);transition:transform .3s,box-shadow .3s;padding:4px;text-align:center}
.tnode.on{transform:translate(-50%,-50%) scale(1.12);box-shadow:0 0 0 6px color-mix(in srgb,var(--c) 25%,transparent)}
.tn-i{font-size:28px;line-height:1}.tn-n{font-size:12.5px;font-weight:700;line-height:1.15;margin-top:3px}
.tcenter{position:absolute;left:50%;top:59.7%;transform:translate(-50%,-50%);width:42%;text-align:center}
.tcenter b{display:block;font-family:Fraunces,Georgia,serif;font-size:clamp(15px,1.7vw,20px);line-height:1.2}
.tcenter span{display:block;font-size:12.5px;color:var(--muted);margin-top:4px;line-height:1.35}
.tcards{display:flex;flex-direction:column;gap:10px}.tcard.on{box-shadow:0 0 0 2px var(--c);transform:translateX(4px)}
/* wheel */
.wheel .seg{cursor:pointer;transition:transform .45s cubic-bezier(.2,.8,.2,1)}
.wheel .seg path{fill:var(--c);opacity:.78;stroke:var(--v-stroke);stroke-width:2;transition:opacity .3s}
.sel-root.focus .seg path{opacity:.35}.wheel .seg.on{transform:translate(var(--tx),var(--ty))}.wheel .seg.on path{opacity:1;filter:drop-shadow(0 0 12px var(--c))}
.wheel text{text-anchor:middle;fill:var(--v-ink);pointer-events:none}.wheel .wi{font-size:24px}.wheel .wn{font-size:14.5px;font-weight:700}.wheel .ws{font-size:11px;opacity:.85}
.wheel .wring{fill:var(--gold);opacity:.6;transform-origin:center;transform-box:view-box;animation:spin 40s linear infinite}
.wheel .wc{fill:var(--panel);stroke:var(--line);stroke-width:2}
.wheel .wct{font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;fill:var(--muted)}.wheel .wcname{font-family:Fraunces,Georgia,serif;font-size:19px;fill:var(--ink)}
.run .wheel .seg{animation:pop .8s cubic-bezier(.2,.8,.2,1) both}
/* trinity */
.trinity .tc{fill:var(--c);opacity:.55;mix-blend-mode:multiply;stroke:var(--v-stroke);stroke-width:2;cursor:pointer;transition:opacity .3s;transform-box:fill-box;transform-origin:center}
:root[data-theme="dark"] .trinity .tc{mix-blend-mode:screen}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .trinity .tc{mix-blend-mode:screen}}
.run .trinity .tc{animation:pop 1s cubic-bezier(.2,.8,.2,1) var(--d) both}
.trinity .tc.on{opacity:.9}.trinity text{text-anchor:middle;fill:var(--ink);pointer-events:none}.trinity .tci{font-size:26px}.trinity .tcn{font-size:15px;font-weight:700}
.trinity .tct{font-family:Fraunces,Georgia,serif;font-size:14px;font-weight:700}
.trinity .tring2{cursor:pointer;transform-origin:center;transform-box:view-box;animation:spin 80s linear infinite}
.trinity .tro{fill:none;stroke:var(--gold);stroke-width:26;opacity:.16}.trinity .tring2.on .tro{opacity:.4}
.trinity .trt{font-size:13px;letter-spacing:.18em;fill:var(--gold);font-weight:700;text-transform:uppercase}
/* vmv */
.vmv{position:relative;display:flex;flex-direction:column;gap:9px;padding-left:46px;max-width:1140px}
.vmv .beam{position:absolute;left:17px;top:30px;bottom:10px;width:3px;background:linear-gradient(var(--gold),var(--acc2),var(--acc));border-radius:3px;opacity:.6}
.vmv .beam i{position:absolute;left:-5px;width:13px;height:13px;border-radius:50%;background:var(--gold);box-shadow:0 0 16px 4px var(--gold);animation:fall 4.5s ease-in infinite}
@keyframes fall{0%{top:0;opacity:0}10%{opacity:1}90%{opacity:1}100%{top:100%;opacity:0}}
.vmv .star{position:absolute;left:4px;top:-4px;font-size:30px;color:var(--gold);text-shadow:0 0 18px var(--gold);animation:pulse 3s ease-in-out infinite}
.vm{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px 18px;box-shadow:var(--shadow);position:relative}
.vm:before{content:"";position:absolute;left:-36px;top:20px;width:13px;height:13px;border-radius:50%;background:var(--panel);border:3px solid var(--c,var(--acc))}
.vm.vision{--c:var(--gold);border-top:4px solid var(--gold)}.vm.mission{--c:var(--acc2);border-top:4px solid var(--acc2)}.vm.identity{--c:var(--acc);border-top:4px solid var(--acc)}
.vm p{font-size:clamp(16px,1.7vw,20px);line-height:1.38;margin:.2em 0 0}
.lbl{display:block;font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700}
.pills{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:9px}
.pill{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--c);border-radius:12px;padding:8px 11px;display:flex;flex-direction:column;gap:1px;font-size:14.5px}
.pill span{font-size:22px}.pill small{color:var(--muted);font-size:13px}
.vals{display:flex;flex-wrap:wrap;gap:8px}
.val{background:var(--chip);border:1px solid var(--line);border-radius:12px;padding:6px 12px;display:flex;flex-direction:column}.val small{color:var(--muted);font-size:12px}
/* ecosystem */
.ecowrap{max-width:1000px;margin:0 auto}.ecofig{position:relative;width:100%;aspect-ratio:1000/640}
.eco{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
.eco .eorbit{fill:none;stroke:var(--gold);stroke-dasharray:2 9;stroke-width:1.5;opacity:.55}
.eco .fl path{fill:none;stroke:var(--line);stroke-width:2.5;stroke-dasharray:6 7;animation:ants 1.6s linear infinite;transition:stroke .3s}
.eco .fl.on path{stroke:var(--acc2);stroke-width:4;stroke-dasharray:none}
.eco .ah{fill:var(--muted)}.eco .edot{fill:var(--acc2);filter:drop-shadow(0 0 6px var(--acc2))}
@keyframes ants{to{stroke-dashoffset:-26}}
.enode{position:absolute;transform:translate(-50%,-50%);width:17%;background:var(--panel);border:2px solid var(--c,var(--acc));border-radius:14px;padding:7px 9px;text-align:center;
box-shadow:var(--shadow);transition:transform .3s,box-shadow .3s;z-index:2}
.enode.hub{width:22%;border-width:3px;border-color:var(--acc2);background:linear-gradient(var(--panel),var(--bg2))}
.enode.on{transform:translate(-50%,-50%) scale(1.07);box-shadow:0 0 0 5px color-mix(in srgb,var(--c,var(--acc2)) 25%,transparent)}
.enode .ei{font-size:22px;display:block;line-height:1.1}.enode b{display:block;font-size:13.5px;line-height:1.2}.enode small{display:block;font-size:11px;color:var(--muted);line-height:1.25;margin-top:2px}
.ecap{text-align:center;min-height:1.6em;color:var(--muted);font-size:15px;margin:6px 0}.ecap b{color:var(--ink)}
.elist{display:none}.eitem{display:flex;gap:10px;align-items:flex-start;background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--c,var(--acc2));border-radius:10px;padding:8px 10px;margin:6px 0}
.eitem small{display:block;color:var(--muted);font-size:13px}.eitem .ei{font-size:20px}
.outs{justify-content:center;align-items:center}.outs .lbl{margin-right:4px}
/* cycle */
.cycle{position:relative;width:min(100%,560px);aspect-ratio:1;margin:0 auto}
.cycle svg{position:absolute;inset:0;width:100%;height:100%}
.cring{fill:none;stroke:var(--line);stroke-width:.7;stroke-dasharray:1.2 1.6}
.cstep{position:absolute;transform:translate(-50%,-50%);display:flex;flex-direction:column;align-items:center;width:23%;text-align:center;transition:transform .3s}
.cstep .cic{width:clamp(40px,8.5vw,58px);aspect-ratio:1;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:clamp(18px,3vw,26px);
background:var(--panel);border:3px solid var(--c);box-shadow:var(--shadow);transition:box-shadow .3s}
.cstep b{font-size:12.5px;line-height:1.2;margin-top:3px}.cstep .cn{font-size:10.5px;color:var(--muted);font-weight:700}
.cstep.on{transform:translate(-50%,-50%) scale(1.13)}.cstep.on .cic{box-shadow:0 0 0 7px color-mix(in srgb,var(--c) 30%,transparent)}
.cdot{position:absolute;width:16px;height:16px;border-radius:50%;background:var(--acc2);box-shadow:0 0 14px 3px var(--acc2);transform:translate(-50%,-50%);left:50%;top:8%}
.ccenter{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:50%;text-align:center}
.cbody{display:flex;flex-direction:column;gap:4px}.cbody .ct{font-family:Fraunces,Georgia,serif;font-size:clamp(16px,2vw,22px)}.cbody .cb{font-size:13.5px;color:var(--muted)}
.cbody.swap{animation:swap .45s ease}
.clist{display:none}.center-note{display:none}
/* chain */
.chain{display:flex;align-items:stretch;gap:0;margin:14px 0;flex-wrap:nowrap}
.cnode{flex:1 1 0;min-width:0;background:var(--panel);border:1px solid var(--line);border-top:5px solid var(--c);border-radius:14px;padding:12px 13px;display:flex;flex-direction:column;gap:3px;box-shadow:var(--shadow)}
.cnode .ci{font-size:26px}.cnode b{font-size:15.5px;line-height:1.25}.cnode small{color:var(--muted);font-size:13px}
.cnode .sub{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--c);font-weight:700}
.carrow{flex:0 0 46px;position:relative;display:flex;align-items:center;justify-content:center;flex-direction:column}
.carrow i{position:relative;display:block;width:100%;height:3px;background:var(--line)}
.carrow i:after{content:"";position:absolute;top:-5px;width:13px;height:13px;border-radius:50%;background:var(--acc2);box-shadow:0 0 10px var(--acc2);animation:slide 1.8s ease-in-out infinite}
.carrow small{position:absolute;top:calc(50% + 10px);font-size:10.5px;color:var(--muted);text-align:center;line-height:1.15;width:70px}
@keyframes slide{from{left:-4px;opacity:0}20%{opacity:1}80%{opacity:1}to{left:calc(100% - 9px);opacity:0}}
/* layers */
.layers{display:grid;grid-template-columns:1fr;gap:16px}.layers.has-arrow{grid-template-columns:minmax(0,1fr) 120px}
.lstack{display:flex;flex-direction:column;gap:10px}
.layer{display:grid;grid-template-columns:minmax(200px,.8fr) minmax(0,2fr);gap:14px;background:var(--panel);border:1px solid var(--line);border-left:6px solid var(--c);
border-radius:14px;padding:12px 16px;box-shadow:var(--shadow)}
.run .layer{animation:rise .7s cubic-bezier(.2,.8,.2,1) var(--d) both}
@keyframes rise{from{opacity:0;transform:translateY(30px) scale(.97)}to{opacity:1;transform:none}}
.lh{display:flex;gap:10px;align-items:flex-start}.lh b{display:block;font-size:16.5px}.lh small{display:block;color:var(--muted);font-size:13px}
.lb p{margin:0 0 4px;font-size:14.5px}
.larrow{position:relative;border-radius:14px;background:linear-gradient(var(--bg2),transparent);display:flex;align-items:center;justify-content:center;overflow:hidden;min-height:200px}
.larrow i{position:absolute;left:50%;width:12px;height:12px;margin-left:-6px;border-radius:50%;background:var(--gold);box-shadow:0 0 12px var(--gold);animation:climb 3s linear infinite}
.larrow i:nth-child(2){animation-delay:1s}.larrow i:nth-child(3){animation-delay:2s}
.larrow.down i{animation-name:fall2}
@keyframes climb{from{top:100%;opacity:0}15%{opacity:1}85%{opacity:1}to{top:0;opacity:0}}
@keyframes fall2{from{top:0;opacity:0}15%{opacity:1}85%{opacity:1}to{top:100%;opacity:0}}
.larrow span{position:relative;writing-mode:vertical-rl;transform:rotate(180deg);font-size:13px;color:var(--muted);font-weight:600;background:var(--bg);padding:8px 4px;border-radius:8px}
.larrow.down span{transform:none}
/* roadmap */
.rm{position:relative;display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:12px;padding-top:6px;--p:0}
.rtrack{position:absolute;left:0;right:0;top:34px;height:5px;background:var(--line);border-radius:5px}
.rfill{position:absolute;left:0;top:0;bottom:0;width:calc(var(--p) * 100%);background:linear-gradient(90deg,var(--gold),var(--acc2),var(--acc));border-radius:5px;transition:width .9s cubic-bezier(.4,0,.2,1)}
.rcomet{position:absolute;top:50%;left:calc(var(--p) * 100%);width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;background:#fff;box-shadow:0 0 0 4px var(--acc2),0 0 22px 6px var(--acc2);transition:left .9s cubic-bezier(.4,0,.2,1)}
.rph{position:relative;display:flex;flex-direction:column;align-items:stretch}
.rnode{height:70px;display:flex;align-items:center;justify-content:center;position:relative}
.rdot{width:44px;height:44px;border-radius:50%;background:var(--panel);border:3px solid var(--line);display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:700;z-index:1;transition:all .5s}
.rph.lit .rdot{border-color:var(--c);box-shadow:0 0 0 6px color-mix(in srgb,var(--c) 25%,transparent);transform:scale(1.1)}
.pin{position:absolute;top:-14px;font-size:11px;font-weight:700;color:var(--acc2);white-space:nowrap;animation:pulse 2s ease-in-out infinite}
.rcard{background:var(--panel);border:1px solid var(--line);border-top:4px solid var(--line);border-radius:12px;padding:11px 13px;opacity:.35;transform:translateY(10px);transition:all .6s;box-shadow:var(--shadow);flex:1}
.rph.lit .rcard{opacity:1;transform:none;border-top-color:var(--c)}
.rwhen{display:block;font-size:11.5px;text-transform:uppercase;letter-spacing:.1em;color:var(--c);font-weight:700}
.rcard b{display:block;font-size:15.5px;line-height:1.25;margin:2px 0}.rgoal{font-size:13.5px;color:var(--muted);margin:4px 0;font-style:italic}
.rcard ul.dots li{font-size:13.5px}
/* scores */
.scores th{cursor:pointer;user-select:none}.scores th span{display:block;font-size:16px}.scores th:hover{color:var(--acc)}
.scores td{white-space:nowrap}.scores td.nm{white-space:normal;min-width:180px}.scores td.nm small{display:block;color:var(--muted);font-weight:400;font-size:12px}
.heat{text-align:center!important;font-weight:600;background:color-mix(in srgb,var(--acc) var(--a),transparent)}
.scores tr.top td.nm,.scores tr.top td.rk{color:var(--acc2)}.scores tr.top{box-shadow:inset 4px 0 0 var(--acc2)}
.tot{min-width:170px}.totw{display:flex;align-items:center;gap:7px}.tot b{font-size:16px}.tot small{color:var(--muted)}.scores td{padding:6px 10px}
.sbar{flex:1;height:8px;background:var(--line);border-radius:8px;overflow:hidden}
.sbar i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--gold),var(--acc2));border-radius:8px;transition:width 1.2s cubic-bezier(.2,.8,.2,1)}
/* compare */
.compare{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:14px;margin:8px 0}
.ccol{position:relative;background:var(--panel);border:1px solid var(--line);border-top:5px solid var(--c);border-radius:14px;padding:14px 16px;box-shadow:var(--shadow)}
.ccol.recd{box-shadow:0 0 0 2px var(--c),0 12px 34px color-mix(in srgb,var(--c) 30%,transparent)}
.rec{position:absolute;top:-13px;right:12px;background:var(--c);color:#fff;font-size:11.5px;font-weight:700;padding:3px 10px;border-radius:99px}
.ccol h3{display:flex;gap:8px;align-items:center;font-size:17.5px}.ccol p{font-size:14.5px;color:var(--muted)}
.pc{font-size:14px;margin-top:8px;padding:8px 10px;border-radius:8px;background:var(--bg2)}.pc b{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.08em}
.pc.pro b{color:var(--ok)}.pc.con b{color:var(--warn)}
.big-q{font-size:clamp(20px,2.6vw,30px);text-align:center;max-width:900px;margin:18px auto 0}
/* questions */
.qs{list-style:none;padding:0;display:flex;flex-direction:column;gap:12px;max-width:1000px}
.qs li{display:flex;gap:16px;align-items:flex-start;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 18px;box-shadow:var(--shadow)}
.qn{flex:0 0 42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-family:Fraunces,Georgia,serif;font-size:20px;color:#fff;background:var(--c)}
.qq{font-family:Fraunces,"Noto Serif",Georgia,serif;font-size:clamp(17px,2vw,22px);margin:0;line-height:1.35}.qh{color:var(--muted);font-size:14px;margin:6px 0 0}
/* image */
figure.img{margin:8px auto;background:#fff;border:1px solid var(--line);border-radius:14px;padding:10px;box-shadow:var(--shadow);max-width:900px}
figure.img img{width:100%;height:auto;display:block;border-radius:8px}figcaption{font-size:13px;color:#5d6656;text-align:center;padding-top:6px}
/* closing */
.closing{position:relative;text-align:center;width:100%}
.closing .hero-art.bg{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;opacity:.22;pointer-events:none}
.closing .hero-art.bg svg{max-width:640px}
.ctitle{font-size:clamp(24px,3vw,36px)}
.cwords{display:flex;flex-wrap:wrap;justify-content:center;gap:10px 26px;margin:20px auto;max-width:1000px;position:relative}
.cw{font-size:clamp(28px,4.6vw,56px);font-weight:600;color:var(--c);text-shadow:0 0 30px color-mix(in srgb,var(--c) 35%,transparent)}
.clines{position:relative}.clines p{font-size:clamp(16px,1.8vw,20px);color:var(--muted);margin:.35em auto;max-width:860px}
.final{position:relative;font-size:clamp(20px,2.6vw,30px);max-width:900px;margin:20px auto 0}
/* HUD */
#bar{position:fixed;top:0;left:0;height:3px;background:linear-gradient(90deg,var(--gold),var(--acc2),var(--acc));z-index:5;transition:width .4s}
#hud{position:fixed;left:0;right:0;bottom:0;height:52px;display:flex;align-items:center;gap:8px;padding:0 max(12px,2vw);z-index:5;
background:linear-gradient(transparent,var(--bg) 45%);font-size:13px;color:var(--muted)}
#chap{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:600}
#hud button{background:var(--panel);border:1px solid var(--line);border-radius:10px;min-width:36px;height:34px;cursor:pointer;font-size:15px;color:var(--ink)}
#hud button:hover{border-color:var(--acc)}#num{min-width:58px;text-align:center;font-variant-numeric:tabular-nums}
#menu{position:fixed;top:0;right:0;bottom:0;width:min(380px,92vw);background:var(--panel);border-left:1px solid var(--line);z-index:6;transform:translateX(105%);
transition:transform .35s;overflow-y:auto;padding:18px 18px 70px;box-shadow:-20px 0 40px rgba(0,0,0,.12)}
#menu.open{transform:none}#menu h4{margin:14px 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.12em;color:var(--acc)}
#menu a{display:block;padding:5px 8px;border-radius:8px;color:var(--ink);text-decoration:none;font-size:14px;cursor:pointer}
#menu a:hover{background:var(--chip)}#menu a.cur{background:var(--hl);font-weight:600}
#menu .mclose{float:right}
.slide.hasmore:after{content:"⌄ more below";position:fixed;bottom:58px;left:50%;transform:translateX(-50%);font-size:12px;color:var(--muted);background:var(--panel);
border:1px solid var(--line);border-radius:99px;padding:2px 10px;pointer-events:none}
/* responsive */
@media (max-width:900px){
 .two,.vgrid,.hero-wrap,.tgrid{grid-template-columns:minmax(0,1fr)}
 .hero-art{order:-1;max-width:260px;margin:0 auto}.hero-wrap{gap:6px}
 .layer{grid-template-columns:minmax(0,1fr);gap:6px}
 .layers.has-arrow{grid-template-columns:minmax(0,1fr) 54px}
 .chain{flex-direction:column}.carrow{flex:0 0 40px;flex-direction:row}.carrow i{width:3px;height:100%;min-height:36px}
 .carrow i:after{left:-5px;animation-name:slidev}.carrow small{position:static;margin-left:10px;width:auto}
 .rm{grid-template-columns:minmax(0,1fr);padding-left:54px;gap:10px}
 .rtrack{left:22px;right:auto;top:0;bottom:0;width:5px;height:auto}
 .rfill{width:auto;right:0;height:calc(var(--p) * 100%);transition:height .9s}
 .rcomet{left:50%;top:calc(var(--p) * 100%);transition:top .9s}
 .rnode{position:absolute;left:-54px;top:0;height:44px;width:48px}.rdot{width:36px;height:36px;font-size:16px}.pin{left:-4px;top:44px;font-size:10px;white-space:normal;width:56px;text-align:center;line-height:1.1}
}
@media (max-width:700px){
 .slide{padding:44px 16px 80px}
 .ecowrap{display:none}.elist{display:block}
 .cycle{display:none}.clist{display:block;list-style:none;padding:0}.clist li{border-left:4px solid var(--c);background:var(--panel);border-radius:8px;padding:8px 10px;margin:6px 0;font-size:14px}
 .center-note{display:block;color:var(--muted);font-style:italic}
 .vrow{grid-template-columns:1fr;gap:2px}
}
@keyframes slidev{from{top:-4px;opacity:0}20%{opacity:1}80%{opacity:1}to{top:calc(100% - 9px);opacity:0}}
.static *,.static *:before,.static *:after{animation:none!important;transition:none!important}
.static .f,.static .rcard{opacity:1;transform:none}
@media (prefers-reduced-motion:reduce){*{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
@media print{
 html,body{overflow:visible;height:auto;background:#fff}#deck{position:static}#hud,#menu,#bar,#stars{display:none}
 .slide{position:relative;opacity:1;visibility:visible;transform:none;overflow:visible;page-break-after:always;min-height:100vh;padding:28px}
 .f,.rcard{opacity:1;transform:none}*{animation:none!important;transition:none!important}
}
"""

JS = r"""
(function(){'use strict';
const $=(q,r=document)=>r.querySelector(q),$$=(q,r=document)=>Array.from(r.querySelectorAll(q));
const slides=$$('#deck>.slide'),N=slides.length;let cur=-1,ftimers=[];
const bar=$('#bar'),num=$('#num'),chap=$('#chap'),menu=$('#menu');const CH=JSON.parse($('#chapdata').textContent);
const W={};const NS='http://www.w3.org/2000/svg';const Q=new URLSearchParams(location.search);const STATIC=Q.has('static');if(STATIC)document.documentElement.classList.add('static');if(Q.get('theme'))document.documentElement.dataset.theme=Q.get('theme');
function T(s){return s._t||(s._t=[])}
function later(s,ms,fn){const id=setTimeout(fn,ms);T(s).push(()=>clearTimeout(id))}
function every(s,ms,fn){const id=setInterval(fn,ms);T(s).push(()=>clearInterval(id))}
function loop(s,fn){let on=true;T(s).push(()=>{on=false});const f=t=>{if(!on)return;fn(t);requestAnimationFrame(f)};requestAnimationFrame(f)}
function clearS(s){(s._t||[]).forEach(f=>f());s._t=[]}
function frags(s){return $$('.f',s)}
function countUp(root){if(STATIC)return;$$('[data-count]',root).forEach(el=>{const to=+el.dataset.count;let k=0;const n=36;clearInterval(el._ci);
 el._ci=setInterval(()=>{k++;el.textContent=Math.round(to*(1-Math.pow(1-k/n,3)));if(k>=n){clearInterval(el._ci);el.textContent=to}},28)})}
function swap(el,html){el.innerHTML=html;el.classList.remove('swap');void el.offsetWidth;el.classList.add('swap')}
/* generic selectable widget: [data-sel] items + template[data-sel] panels + optional tour */
function selector(s,o){o=o||{};const root=o.root||$('.sel-root',s)||s;const items=$$('[data-sel]',root).filter(e=>e.tagName!=='TEMPLATE');
 const keys=o.tour||[...new Set(items.map(e=>e.dataset.sel))];const panel=$('.selpanel',s),btn=$('.seltour',s);let i=-1,auto=true;
 function sel(k){items.forEach(e=>e.classList.toggle('on',e.dataset.sel===k));root.classList.add('focus');if(o.hl)o.hl(k);
  const tp=$('template[data-sel="'+k+'"]',s);if(tp&&panel)swap(panel,tp.innerHTML);if(o.on)o.on(k)}
 function setAuto(v){auto=v;if(btn)btn.textContent=v?'⏸ Pause':'▶ Play'}
 items.forEach(e=>{e.onclick=ev=>{ev.stopPropagation();setAuto(false);i=keys.indexOf(e.dataset.sel);sel(e.dataset.sel)}});
 if(btn)btn.onclick=ev=>{ev.stopPropagation();setAuto(!auto)};
 items.forEach(e=>e.classList.remove('on'));root.classList.remove('focus');setAuto(true);i=-1;
 const t0=$('template[data-sel="intro"]',s);if(t0&&panel)panel.innerHTML=t0.innerHTML;
 if(STATIC){setAuto(false);const k=Q.get('sel');if(k&&keys.includes(k))sel(k);return}
 later(s,o.delay||2200,()=>{const step=()=>{if(!auto)return;i=(i+1)%keys.length;sel(keys[i])};step();every(s,o.period||3800,step)})}
W.venn={enter(s){const svg=$('svg.venn',s),nar=s.clientWidth<760;svg.setAttribute('viewBox',nar?svg.dataset.vbn:svg.dataset.vb);svg.classList.toggle('narrow',nar);
 const SET={love:'L',good:'G',need:'N',paid:'P'};
 selector(s,{root:$('.vgrid',s),tour:JSON.parse(svg.dataset.tour),delay:2900,period:3900,
  hl(k){$$('.rg',svg).forEach(r=>r.classList.toggle('on',SET[k]?r.dataset.sets.includes(SET[k]):r.dataset.sel===k));svg.classList.add('focus')}})},
 leave(s){const svg=$('svg.venn',s);svg.classList.remove('focus')}};
W.petals={enter(s){selector(s,{delay:2000})}};
W.wheel={enter(s){const nm=$('.wcname',s);selector(s,{delay:1400,period:4200,on(k){const g=$('.seg[data-sel="'+k+'"]',s);if(nm&&g)nm.textContent=g.dataset.name}})}};
W.trinity={enter(s){selector(s,{delay:1600,period:4000})}};
W.triad={enter(s){selector(s,{root:$('.tgrid',s),delay:1500,period:3400})}};
W.ecosystem={enter(s){const svg=$('svg.eco',s);if(!svg)return;const flows=$$('.fl',svg),cap=$('.ecap',s),nodes=$$('.enode',s);let i=-1,dot=null;if(!flows.length)return;
 function move(f){const p=$('path',f),L=p.getTotalLength();if(!dot){dot=document.createElementNS(NS,'circle');dot.setAttribute('r',9);dot.setAttribute('class','edot');svg.appendChild(dot)}
  const t0=performance.now();const go=t=>{const k=Math.min(1,(t-t0)/1500),e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2,pt=p.getPointAtLength(L*e);
   dot.setAttribute('cx',pt.x);dot.setAttribute('cy',pt.y);if(k<1&&s.classList.contains('active'))requestAnimationFrame(go)};requestAnimationFrame(go)}
 function step(){i=(i+1)%flows.length;const f=flows[i];flows.forEach(x=>x.classList.toggle('on',x===f));
  nodes.forEach(n=>n.classList.toggle('on',n.dataset.id===f.dataset.from||n.dataset.id===f.dataset.to));cap.innerHTML=f.dataset.cap;move(f)}
 if(STATIC){step();return}later(s,1300,()=>{step();every(s,2700,step)})}};
W.cycle={enter(s){const c=$('.cycle',s);if(!c||!c.offsetParent)return;const steps=$$('.cstep',c),n=steps.length,dot=$('.cdot',c),body=$('.cbody',c);
 const period=+c.dataset.period||n*2600;let last=-1;const t0=performance.now();
 if(STATIC){steps[0].classList.add('on');const tp=$('template[data-i="0"]',c);if(tp)body.innerHTML=tp.innerHTML;return}
 loop(s,t=>{const a=((t-t0)/period)%1,ang=a*2*Math.PI-Math.PI/2;dot.style.left=(50+42*Math.cos(ang))+'%';dot.style.top=(50+42*Math.sin(ang))+'%';
  const k=Math.floor(a*n+0.02)%n;if(k!==last){last=k;steps.forEach((e,j)=>e.classList.toggle('on',j===k));const tp=$('template[data-i="'+k+'"]',c);if(tp)swap(body,tp.innerHTML)}})}};
W.roadmap={enter(s){const rm=$('.rm',s),ph=$$('.rph',rm),n=ph.length;rm.style.setProperty('--p',0);ph.forEach(p=>p.classList.remove('lit'));
 if(STATIC){rm.style.setProperty('--p',1);ph.forEach(p=>p.classList.add('lit'));return}
 ph.forEach((p,k)=>later(s,600+k*950,()=>{rm.style.setProperty('--p',(k+.5)/n);later(s,500,()=>p.classList.add('lit'))}));
 later(s,700+n*950,()=>rm.style.setProperty('--p',1))}};
W.scores={enter(s){const bars=$$('.sbar i',s);if(STATIC)bars.forEach(b=>b.style.width=b.dataset.w);else{bars.forEach(b=>b.style.width='0');later(s,350,()=>bars.forEach(b=>b.style.width=b.dataset.w))}
 const tb=$('tbody',s);$$('th[data-sort]',s).forEach(th=>{th.onclick=()=>{const k=th.dataset.sort;const rows=$$('tr',tb);
  rows.sort((a,b)=>{if(k==='name')return a.cells[1].textContent.localeCompare(b.cells[1].textContent);const kk='s'+k;return (+b.dataset[kk])-(+a.dataset[kk])||(+a.dataset.r)-(+b.dataset.r)});
  rows.forEach((r,j)=>{r.cells[0].textContent=j+1;tb.appendChild(r)})}})}};
function enter(s){s.classList.remove('run');void s.offsetWidth;s.classList.add('run');const w=W[s.dataset.type];if(w&&w.enter)w.enter(s);countUp(s)}
function leave(s){clearS(s);s.classList.remove('run');const w=W[s.dataset.type];if(w&&w.leave)w.leave(s)}
function moreBelow(s){return s.scrollTop+s.clientHeight<s.scrollHeight-30}
function updMore(s){s.classList.toggle('hasmore',moreBelow(s))}
slides.forEach(s=>s.addEventListener('scroll',()=>updMore(s),{passive:true}));
function show(i,back){i=Math.max(0,Math.min(N-1,i));if(i===cur)return;const old=slides[cur];if(old)leave(old);
 ftimers.forEach(clearTimeout);ftimers=[];slides.forEach((s,k)=>{s.classList.toggle('active',k===i);s.classList.toggle('prev',k<i)});
 cur=i;const s=slides[i];s.scrollTop=0;const fs=frags(s);
 if(back||STATIC)fs.forEach(f=>f.classList.add('on'));else{fs.forEach(f=>f.classList.remove('on'));fs.forEach((f,k)=>ftimers.push(setTimeout(()=>f.classList.add('on'),160+k*190)))}
 enter(s);bar.style.width=((i+1)/N*100)+'%';num.textContent=(i+1)+' / '+N;chap.textContent=CH[s.dataset.ch]||'';
 $$('#menu a[data-i]').forEach(a=>a.classList.toggle('cur',+a.dataset.i===i));try{history.replaceState(null,'','#'+(i+1))}catch(e){}
 setTimeout(()=>updMore(s),900)}
function next(){const s=slides[cur],hidden=frags(s).filter(f=>!f.classList.contains('on'));
 if(hidden.length){ftimers.forEach(clearTimeout);hidden.forEach(f=>f.classList.add('on'));return}
 if(moreBelow(s)){s.scrollBy({top:s.clientHeight*.8,behavior:'smooth'});return}show(cur+1)}
function prev(){show(cur-1,true)}
function goChapter(c){const i=slides.findIndex(s=>s.dataset.ch===c);if(i>=0){show(i);menu.classList.remove('open')}}
$$('[data-goto]').forEach(a=>a.onclick=e=>{e.stopPropagation();goChapter(a.dataset.goto)});
$$('#menu a[data-i]').forEach(a=>a.onclick=()=>{show(+a.dataset.i);menu.classList.remove('open')});
const root=document.documentElement;try{const t=localStorage.getItem('ikigai-theme');if(t&&!Q.get('theme'))root.dataset.theme=t}catch(e){}
function toggleTheme(){const dark=root.dataset.theme?root.dataset.theme==='dark':matchMedia('(prefers-color-scheme: dark)').matches;root.dataset.theme=dark?'light':'dark';
 try{localStorage.setItem('ikigai-theme',root.dataset.theme)}catch(e){}}
$('#b-prev').onclick=prev;$('#b-next').onclick=next;$('#b-menu').onclick=()=>menu.classList.toggle('open');$('#b-theme').onclick=toggleTheme;
$('#b-print').onclick=()=>{slides.forEach(s=>frags(s).forEach(f=>f.classList.add('on')));window.print()};$('.mclose').onclick=()=>menu.classList.remove('open');
document.addEventListener('keydown',e=>{if(e.target.closest('input,textarea'))return;const k=e.key;
 if(['ArrowRight','PageDown',' ','Enter'].includes(k)){e.preventDefault();next()}else if(['ArrowLeft','PageUp','Backspace'].includes(k)){e.preventDefault();prev()}
 else if(k==='Home')show(0);else if(k==='End')show(N-1);else if(k==='m'||k==='M')menu.classList.toggle('open');else if(k==='t'||k==='T')toggleTheme();
 else if(k==='Escape')menu.classList.remove('open')});
let tx=null,ty=null;document.addEventListener('touchstart',e=>{tx=e.touches[0].clientX;ty=e.touches[0].clientY},{passive:true});
document.addEventListener('touchend',e=>{if(tx===null)return;const dx=e.changedTouches[0].clientX-tx,dy=e.changedTouches[0].clientY-ty;
 if(Math.abs(dx)>60&&Math.abs(dx)>Math.abs(dy)*1.5){dx<0?next():prev()}tx=null},{passive:true});
let resizeT;addEventListener('resize',()=>{clearTimeout(resizeT);resizeT=setTimeout(()=>{const s=slides[cur];if(s){leave(s);enter(s)}},300)});
const h=parseInt((location.hash||'').slice(1),10);show(h>0?h-1:0);
/* stars */
(function(){const c=$('#stars');if(!c||!c.getContext)return;const x=c.getContext('2d');let w,h,st=[],col='#fff',fr=0;
 const RM=matchMedia('(prefers-reduced-motion: reduce)').matches;
 function rs(){const d=devicePixelRatio||1;w=c.width=innerWidth*d;h=c.height=innerHeight*d;
  st=Array.from({length:120},()=>({x:Math.random()*w,y:Math.random()*h,r:(Math.random()*1.3+.3)*d,p:Math.random()*6.28,s:.3+Math.random()*.9}))}
 rs();addEventListener('resize',rs);
 function draw(t){if(fr++%60===0)col=getComputedStyle(root).getPropertyValue('--star').trim()||'#fff';x.clearRect(0,0,w,h);x.fillStyle=col;
  for(const s of st){x.globalAlpha=(.2+.8*Math.abs(Math.sin(s.p+t/1000*s.s)))*.5;x.beginPath();x.arc(s.x,s.y,s.r,0,6.283);x.fill()}
  if(!RM&&!STATIC)requestAnimationFrame(draw)}requestAnimationFrame(draw)})();
})();
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500;600;700;800'
         '&family=Noto+Serif:wght@400;600&family=Noto+Serif+Devanagari:wght@400;600&display=swap" rel="stylesheet">')


def load_spec(path) -> dict:
    p = pathlib.Path(path)
    if p.suffix == ".py":
        return runpy.run_path(str(p))["SPEC"]
    return json.loads(p.read_text(encoding="utf-8"))


def validate(spec: dict) -> list[str]:
    errs = []
    if "slides" not in spec or not spec["slides"]:
        return ["spec has no slides"]
    chs = {c["id"] for c in spec.get("chapters", [])}
    for i, s in enumerate(spec["slides"]):
        t = s.get("type")
        where = f"slide {i + 1} ({t}: {plain(s.get('title', ''))[:40]})"
        if t not in R:
            errs.append(f"{where}: unknown type '{t}'. Known: {', '.join(sorted(R))}")
            continue
        for k in R[t][1]:
            if k not in s:
                errs.append(f"{where}: missing required field '{k}'")
        if chs and s.get("ch") not in chs:
            errs.append(f"{where}: chapter '{s.get('ch')}' is not declared in chapters")
        if t == "triad" and len(s.get("nodes", [])) != 3:
            errs.append(f"{where}: triad needs exactly 3 nodes")
        if t == "scores":
            n = len(s.get("criteria", []))
            for it in s.get("items", []):
                if len(it.get("scores", [])) != n:
                    errs.append(f"{where}: '{it.get('name')}' has {len(it.get('scores', []))} scores, expected {n}")
        if t == "venn":
            for k in s.get("circles", {}):
                if k not in QUAD:
                    errs.append(f"{where}: circles key '{k}' must be one of love/good/need/paid")
        if t == "ecosystem":
            ids = {"hub"} | {n_["id"] for n_ in s.get("nodes", [])}
            for f in s.get("flows", []):
                for e in ("from", "to"):
                    if f.get(e) not in ids:
                        errs.append(f"{where}: flow {e} '{f.get(e)}' is not a node id")
    return errs


def build_html(spec: dict, base_dir=".") -> str:
    meta = spec.get("meta", {})
    chapters = spec.get("chapters", [])
    ctx = {"chapters": chapters, "base": pathlib.Path(base_dir)}
    out, menu = [], {}
    for i, s in enumerate(spec["slides"]):
        ctx["idx"] = i
        fn = R[s["type"]][0]
        inner = fn(s, ctx)
        center = " center" if s.get("center_v") else ""
        title = plain(s.get("title") or s.get("kicker") or s["type"])
        out.append(f'<section class="slide t-{s["type"]}{center}" data-type="{s["type"]}" data-ch="{esc(s.get("ch", ""))}" id="s{i + 1}"><div class="wrap">{inner}</div></section>')
        menu.setdefault(s.get("ch", ""), []).append((i, title))
    chmap = {c["id"]: plain(c["title"]) for c in chapters}
    menu_html = '<button class="mclose seltour" type="button">✕</button><h3 class="serif">Contents</h3>'
    for c in chapters + ([{"id": ""}] if "" in menu else []):
        if c["id"] not in menu:
            continue
        menu_html += f'<h4>{esc(c.get("icon", ""))} {esc(chmap.get(c["id"], ""))}</h4>'
        menu_html += "".join(f'<a data-i="{i}">{i + 1}. {esc(t)}</a>' for i, t in menu[c["id"]])
    title = esc(meta.get("title", "Life Ikigai Architecture"))
    chapjson = json.dumps(chmap, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html><html lang="{esc(meta.get('lang', 'en'))}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<meta name="description" content="{esc(meta.get('description', ''))}">{FONTS if meta.get('fonts', True) else ''}
<style>{CSS}</style></head><body>
<canvas id="stars" aria-hidden="true"></canvas><div id="bar"></div>
<main id="deck">{''.join(out)}</main>
<nav id="menu" aria-label="Contents">{menu_html}</nav>
<div id="hud"><span id="chap"></span><button id="b-prev" type="button" title="Previous (←)">‹</button><span id="num"></span>
<button id="b-next" type="button" title="Next (→ / Space)">›</button><button id="b-menu" type="button" title="Contents (M)">☰</button>
<button id="b-theme" type="button" title="Theme (T)">◐</button><button id="b-print" type="button" title="Print / PDF">⎙</button></div>
<script type="application/json" id="chapdata">{chapjson}</script>
<script>{JS}</script></body></html>"""


TYPE_DOCS = {
    "hero": "Opening title. title, kicker, jp, subtitle, tagline",
    "agenda": "Auto-built chapter cards (click to jump). skip=[chapter ids]",
    "statement": "Big quote and/or revealed lines. quote, lines[], sanskrit, attribution",
    "text": "Paragraphs/bullets. paras[], bullets[], quote",
    "cards": "Grid of cards. cards[{icon,title,body,tag,color,remedy,points[]}], columns, tone ('warn'), rainbow",
    "table": "Table. columns[], rows[[...]], highlight[idx], compact",
    "venn": "Interactive 4-circle Ikigai. circles{love,good,need,paid:{title,question,items[],summary,label}}, overlaps{passion,mission,profession,vocation:{expression,pitfall,correction}}, lenses{t_no_need,...}, center{title,statement,sub}",
    "petals": "N-petal bloom (e.g. 6-dimension Ikigai). dims[{icon,name,question,expression,color,score?}], center",
    "triad": "Three nodes in a triangle + cards. nodes[3]{icon,name,body,tag,color}, center{title,body}",
    "wheel": "Segmented wheel (e.g. Pancakrtya). segments[{icon,name,sub,body,rows{label:value},color}], center",
    "trinity": "3 overlapping circles in a ring. circles[3]{icon,name,aspiration,question,color}, outer{name,words[],question,body}, center",
    "vmv": "Vision -> mission -> pillars -> values -> identity cascade. vision, mission, pillars[], values[{name,desc}], identity{title,body}",
    "ecosystem": "Hub + orbiting nodes + animated flows. hub{icon,title,body}, nodes[{id,icon,title,body}], flows[{from,to,label}], outcomes[]",
    "cycle": "Circular loop with travelling dot. steps[{icon,title,body}], center, period(ms)",
    "chain": "Left-to-right progression with flowing packets. nodes[{icon,title,body,sub,via}]",
    "layers": "Stacked layers built bottom-up. layers[{icon,title,purpose,body,items[]}], arrow{label,direction up|down}",
    "roadmap": "Timeline with travelling comet. phases[{when,title,goal,items[],icon}], now(index)",
    "scores": "Heatmap ranking with animated totals. criteria[{icon,name,desc}], items[{name,scores[],note}], max, top",
    "compare": "Side-by-side options. columns[{icon,title,tag,body,points[],pros,cons,recommended}], question",
    "questions": "Numbered reflection prompts. prompts[{q,hint}]",
    "image": "Embedded image (base64). src (relative to spec), caption, credit, paras[], bullets[]",
    "closing": "Closing words cascade. words[], lines[], final, title, kicker",
}
