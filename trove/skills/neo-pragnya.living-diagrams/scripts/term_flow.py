#!/usr/bin/env python3
"""term_flow.py: turn a terminal session into an animated, self-explaining SVG.

The left panel is a terminal that types each command and prints its (real) output. The right panel is a rail of
numbered steps that light up in sync and tick off as each command finishes. Everything is CSS keyframes inside one
self-contained SVG, so it animates on GitHub (in an <img>), in docs sites and in slides. With prefers-reduced-motion
the viewer sees the finished session (the resting state *is* the final frame).

    python term_flow.py spec.json --out docs/assets/flows/          # one or many specs (a list) per file
    python term_flow.py specs.py  --out site/public/flows/          # a Python file defining SPECS = [...]

Spec (JSON or Python dict):
    {
      "id": "quickstart",                       # output file name: <id>.svg
      "title": "From zero to verified",          # heading above the panels
      "subtitle": "Six real commands …",         # optional
      "theme": {...},                            # optional colour overrides, see THEMES
      "width": 1200,                             # optional (height is computed)
      "rows": 16,                                # terminal rows visible before it scrolls
      "steps": [{"title": "Initialise", "text": "Creates .ananke/ …"}, …],
      "session": [
        {"cmd": "ananke init", "step": 0,
         "out": ["✓ Ananke project initialized.", {"text": "config  .ananke/config.toml", "tone": "muted"}]},
        …
      ]
    }
Output line tones: ok, warn, err, muted, accent, plain (default). Lines starting with ✓ are ok, ✗/! warn, # muted.

Use real output. Trim long paths and tables, but never invent results: the walkthrough is documentation.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

THEMES: dict[str, dict[str, str]] = {
    "night": {  # celestial navy + gold (Ananke)
        "bg": "#071331", "panel": "#0b1838", "bar": "#13224a", "ink": "#e8eeff", "muted": "#93a3c8",
        "accent": "#f0cf7a", "accent2": "#8fb0ff", "ok": "#5fd3a8", "warn": "#ffb36b", "err": "#ff8a8a",
        "card": "#0f2563", "card_on": "#16307a", "line": "#2a3d6e", "title": "#ffffff",
    },
    "paper": {  # light pastel (Dex Trove)
        "bg": "#fffaf0", "panel": "#1f1d2b", "bar": "#2c2940", "ink": "#f3f0ff", "muted": "#a8a3c0",
        "accent": "#ff7a59", "accent2": "#a78bfa", "ok": "#7fd88f", "warn": "#ffd84d", "err": "#ff8fb1",
        "card": "#ffffff", "card_on": "#fff3dc", "line": "#efe7d6", "title": "#1f1d2b",
    },
}
MONO = "'JetBrains Mono','SFMono-Regular',Menlo,Consolas,monospace"
SANS = "Inter,ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif"


def _tone(line: str | dict[str, str]) -> tuple[str, str]:
    if isinstance(line, dict):
        return line["text"], line.get("tone", "plain")
    s = line.lstrip()
    if s.startswith("✓"):
        return line, "ok"
    if s.startswith(("✗", "!", "BLOCKED")):
        return line, "warn"
    if s.startswith("#"):
        return line, "muted"
    return line, "plain"


def _wrap(text: str, width: int) -> list[str]:
    if len(text) <= width:
        return [text]  # keep indentation and column spacing exactly
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    if cur:
        lines.append(cur)
    return lines


def _shell_wrap(cmd: str, width: int) -> list[str]:
    """Split a long command at spaces into shell continuation lines ("… \\"), keeping quoted strings intact."""
    if len(cmd) <= width:
        return [cmd]
    tokens, cur, quote = [], "", ""
    for ch in cmd:
        if ch in "\"'" and (not quote or quote == ch):
            quote = "" if quote else ch
        if ch == " " and not quote:
            tokens.append(cur)
            cur = ""
        else:
            cur += ch
    tokens.append(cur)
    out, line = [], ""
    for tok in tokens:
        candidate = f"{line} {tok}" if line else tok
        if len(candidate) + 2 > width and line:
            out.append(line + " \\")
            line = "  " + tok
        else:
            line = candidate
    out.append(line)
    return out


class Timeline:
    """Collects (selector, keyframes) pairs on one shared loop of `total` seconds."""

    def __init__(self) -> None:
        self.rules: list[str] = []
        self.n = 0

    def anim(self, cls: str, frames: list[tuple[float, str]], total: float) -> None:
        self.n += 1
        name = f"k{self.n}"
        pct = []
        for t, decl in frames:
            p = max(0.0, min(100.0, 100.0 * t / total))
            pct.append(f"{p:.3f}%{{{decl}}}")
        self.rules.append(f"@keyframes {name}{{{''.join(pct)}}}")
        self.rules.append(f".{cls}{{animation:{name} {total:.2f}s linear infinite both}}")


def render(spec: dict[str, Any]) -> str:
    theme = {**THEMES["night"], **(THEMES.get(spec.get("theme_name", ""), {})), **spec.get("theme", {})}
    W = int(spec.get("width", 1200))
    rows = int(spec.get("rows", 16))
    steps = spec["steps"]
    session = spec["session"]
    fs = 13.5  # terminal font size
    cw = fs * 0.6  # monospace advance
    lh = fs * 1.62
    pad = 24
    top = 92 if spec.get("subtitle") else 72
    term_w = int(W * 0.6) - pad
    cols = int((term_w - 36) / cw)
    rail_x = pad + term_w + 22
    rail_w = W - rail_x - pad
    term_h = int(rows * lh + 58)

    # --- lay out terminal lines and the timeline --------------------------------------------------------------
    lines: list[dict[str, Any]] = []  # {"y", "text", "tone", "kind", "t0", "t1"}
    t = 0.8
    step_on: dict[int, float] = {}
    step_done: dict[int, float] = {}
    for entry in session:
        cmd = entry["cmd"]
        k = entry.get("step")
        if k is not None and k not in step_on:
            step_on[k] = t
        for j, chunk in enumerate(_shell_wrap(cmd, cols - 2)):
            typing = min(1.6, 0.3 + len(chunk) / 34)
            lines.append({"text": chunk, "tone": "cmd", "kind": "cmd" if j == 0 else "cont", "t0": t, "t1": t + typing})
            t += typing + 0.08
        t += 0.27
        for raw in entry.get("out", []):
            text, tone = _tone(raw)
            for part in _wrap(text, cols) or [""]:
                lines.append({"text": part, "tone": tone, "kind": "out", "t0": t, "t1": t + 0.12})
                t += 0.11
        if entry.get("note"):
            for part in _wrap("# " + entry["note"], cols):
                lines.append({"text": part, "tone": "muted", "kind": "out", "t0": t, "t1": t + 0.12})
                t += 0.11
        lines.append({"text": "", "tone": "plain", "kind": "gap", "t0": t, "t1": t})
        t += float(entry.get("pause", 0.9))
        if k is not None:
            step_done[k] = t - 0.5
    hold = float(spec.get("hold", 4.0))
    total = t + hold
    fade = total - 0.6  # everything resets in the last 0.6 s, then the loop restarts

    tl = Timeline()
    body: list[str] = []
    term_x = pad
    text_x = term_x + 18
    first_y = top + 46
    for i, ln in enumerate(lines):
        ln["y"] = first_y + i * lh

    # scrolling: when a line would fall below the visible rows, shift the content up (smoothly, 0.2 s)
    view_bottom = first_y + (rows - 1) * lh
    frames: list[tuple[float, str]] = [(0, "transform:translateY(0px)")]
    shift = 0.0
    for ln in lines:
        need = max(0.0, ln["y"] - view_bottom)
        if need > shift + 0.1:
            frames.append((ln["t0"], f"transform:translateY({-shift:.1f}px)"))
            shift = need
            frames.append((ln["t0"] + 0.2, f"transform:translateY({-shift:.1f}px)"))
    frames += [(fade, f"transform:translateY({-shift:.1f}px)"), (total, "transform:translateY(0px)")]
    final_scroll = -shift

    tones = {"ok": theme["ok"], "warn": theme["warn"], "err": theme["err"], "muted": theme["muted"],
             "accent": theme["accent"], "plain": theme["ink"], "cmd": theme["ink"]}
    content: list[str] = []
    for i, ln in enumerate(lines):
        if ln["kind"] == "gap":
            continue
        y = ln["y"]
        # SVG collapses runs of spaces; non-breaking spaces keep columns and indentation in every renderer
        esc = html.escape(ln["text"]).replace(" ", "\u00a0")
        if ln["kind"] in ("cmd", "cont"):
            width = (len(ln["text"]) + 2) * cw
            cls = f"c{i}"
            caret = f"k{i}"
            prompt = f'<text x="{text_x}" y="{y:.1f}" fill="{theme["accent"]}" font-weight="700">$</text>' if ln["kind"] == "cmd" else ""
            content.append(
                prompt
                + f'<text x="{text_x + 2 * cw:.1f}" y="{y:.1f}" fill="{tones["cmd"]}">{esc}</text>'
                # a cover the colour of the panel slides right to "type" the command; a caret rides its left edge
                f'<g class="{cls}" transform="translate({width + 4:.1f} 0)">'
                f'<rect x="{text_x + 2 * cw - 1:.1f}" y="{y - fs:.1f}" width="{width + 12:.1f}" height="{lh:.1f}" fill="{theme["panel"]}"/>'
                f'<rect class="{caret}" x="{text_x + 2 * cw - 1:.1f}" y="{y - fs + 1:.1f}" width="{cw * 0.9:.1f}" height="{fs + 3:.1f}" fill="{theme["accent"]}" opacity="0"/>'
                "</g>"
            )
            tl.anim(caret, [(0, "opacity:0"), (ln["t0"], "opacity:0"), (ln["t0"] + 0.01, "opacity:.85"),
                            (ln["t1"] + 0.25, "opacity:.85"), (ln["t1"] + 0.3, "opacity:0"), (total, "opacity:0")], total)
            tl.anim(cls, [(0, "transform:translate(0px,0px)"), (ln["t0"], "transform:translate(0px,0px)"),
                          (ln["t1"], f"transform:translate({width + 4:.1f}px,0px)"),
                          (fade, f"transform:translate({width + 4:.1f}px,0px)"), (total, "transform:translate(0px,0px)")], total)
            # the prompt itself appears just before typing starts
            pcls = f"p{i}"
            content[-1] = f'<g class="{pcls}">' + content[-1] + "</g>"
            tl.anim(pcls, [(0, "opacity:0"), (ln["t0"] - 0.15, "opacity:0"), (ln["t0"], "opacity:1"),
                           (fade, "opacity:1"), (total, "opacity:0")], total)
        else:
            cls = f"o{i}"
            content.append(f'<text class="{cls}" x="{text_x}" y="{y:.1f}" fill="{tones[ln["tone"]]}">{esc}</text>')
            tl.anim(cls, [(0, "opacity:0"), (ln["t0"], "opacity:0"), (ln["t1"], "opacity:1"),
                          (fade, "opacity:1"), (total, "opacity:0")], total)

    tl.anim("scroll", frames, total)
    clip_top = top + 32
    body.append(
        f'<clipPath id="tv"><rect x="{term_x}" y="{clip_top}" width="{term_w}" height="{term_h - 40}"/></clipPath>'
        f'<rect x="{term_x}" y="{top}" width="{term_w}" height="{term_h}" rx="12" fill="{theme["panel"]}" stroke="{theme["line"]}"/>'
        f'<rect x="{term_x}" y="{top}" width="{term_w}" height="30" rx="12" fill="{theme["bar"]}"/>'
        f'<rect x="{term_x}" y="{top + 18}" width="{term_w}" height="12" fill="{theme["bar"]}"/>'
        + "".join(f'<circle cx="{term_x + 18 + i * 16}" cy="{top + 15}" r="5" fill="{c}"/>' for i, c in enumerate(["#ff6159", "#ffbd2e", "#28c941"]))
        + f'<text x="{term_x + term_w / 2:.0f}" y="{top + 19}" text-anchor="middle" fill="{theme["muted"]}" font-size="11.5" font-family="{SANS}">{html.escape(spec.get("terminal_title", "zsh — project"))}</text>'
        f'<g clip-path="url(#tv)"><g class="scroll" style="transform:translateY({final_scroll:.1f}px);white-space:pre" xml:space="preserve" font-family="{MONO}" font-size="{fs}">{"".join(content)}</g></g>'
    )

    # --- step rail -----------------------------------------------------------------------------------------
    card_h = max(58.0, (term_h - (len(steps) - 1) * 10) / len(steps))
    for k, step in enumerate(steps):
        y = top + k * (card_h + 10)
        on = step_on.get(k, 0.0)
        done = step_done.get(k, on + 1.0)
        cls_card, cls_tick, cls_num = f"s{k}", f"t{k}", f"n{k}"
        text_lines = _wrap(step.get("text", ""), int((rail_w - 64) / 6.4))[:3]
        body.append(
            f'<g class="{cls_card}">'
            f'<rect x="{rail_x}" y="{y:.1f}" width="{rail_w}" height="{card_h:.1f}" rx="10" fill="{theme["card"]}" stroke="{theme["line"]}"/>'
            f'<rect class="{cls_num}" x="{rail_x}" y="{y:.1f}" width="4" height="{card_h:.1f}" rx="2" fill="{theme["accent"]}"/>'
            f'<circle cx="{rail_x + 26}" cy="{y + 24:.1f}" r="12" fill="none" stroke="{theme["accent"]}" stroke-width="1.6"/>'
            f'<text x="{rail_x + 26}" y="{y + 28.5:.1f}" text-anchor="middle" fill="{theme["accent"]}" font-size="12" font-weight="700" font-family="{SANS}">{k + 1}</text>'
            f'<text x="{rail_x + 48}" y="{y + 29:.1f}" fill="{theme["title"] if theme["card"] != "#ffffff" else theme["title"]}" font-size="14" font-weight="700" font-family="{SANS}">{html.escape(step["title"])}</text>'
            + "".join(f'<text x="{rail_x + 48}" y="{y + 47 + j * 15:.1f}" fill="{theme["muted"]}" font-size="11.5" font-family="{SANS}">{html.escape(tx)}</text>' for j, tx in enumerate(text_lines))
            + f'<g class="{cls_tick}"><circle cx="{rail_x + rail_w - 20}" cy="{y + 22:.1f}" r="9" fill="{theme["ok"]}"/>'
            f'<path d="M{rail_x + rail_w - 24.5} {y + 22:.1f} l3.2 3.4 l6 -6.6" fill="none" stroke="{theme["panel"]}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></g>'
            "</g>"
        )
        tl.anim(cls_card, [(0, "opacity:.38"), (on, "opacity:.38"), (on + 0.25, "opacity:1"), (fade, "opacity:1"), (total, "opacity:.38")], total)
        tl.anim(cls_num, [(0, "opacity:0"), (on, "opacity:0"), (on + 0.2, "opacity:1"), (done, "opacity:1"), (done + 0.3, "opacity:.35"),
                          (fade, "opacity:.35"), (total, "opacity:0")], total)
        tl.anim(cls_tick, [(0, "opacity:0;transform:scale(.4)"), (done, "opacity:0;transform:scale(.4)"),
                           (done + 0.25, "opacity:1;transform:scale(1)"), (fade, "opacity:1;transform:scale(1)"), (total, "opacity:0;transform:scale(.4)")], total)
        body.append(f"<style>.{cls_tick}{{transform-box:fill-box;transform-origin:center}}</style>")

    H = int(top + max(term_h, len(steps) * (card_h + 10) - 10) + pad)
    head = (
        f'<text x="{pad}" y="40" fill="{theme["title"]}" font-size="22" font-weight="800" font-family="{SANS}">{html.escape(spec["title"])}</text>'
        + (f'<text x="{pad}" y="64" fill="{theme["muted"]}" font-size="13.5" font-family="{SANS}">{html.escape(spec["subtitle"])}</text>' if spec.get("subtitle") else "")
    )
    style = (
        "<style>"
        + "".join(tl.rules)
        + "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"
        "</style>"
    )
    desc = html.escape(" ".join(f"$ {e['cmd']}" for e in session))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
        f'aria-labelledby="t d"><title id="t">{html.escape(spec["title"])}</title><desc id="d">{desc}</desc>'
        f'<rect width="{W}" height="{H}" rx="16" fill="{theme["bg"]}"/>{style}{head}{"".join(body)}</svg>'
    )


def load(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".py":
        mod_spec = importlib.util.spec_from_file_location("term_specs", path)
        assert mod_spec and mod_spec.loader
        mod = importlib.util.module_from_spec(mod_spec)
        mod_spec.loader.exec_module(mod)
        specs = mod.SPECS
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        specs = data if isinstance(data, list) else [data]
    for s in specs:
        for key in ("id", "title", "steps", "session"):
            if key not in s:
                raise SystemExit(f"{path}: spec is missing '{key}'")
        n = len(s["steps"])
        for e in s["session"]:
            if e.get("step") is not None and not 0 <= e["step"] < n:
                raise SystemExit(f"{path}: {s['id']}: command {e['cmd']!r} points at step {e['step']}, but there are {n} steps")
    return specs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out", type=Path, default=Path("."))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for spec in load(args.spec):
        target = args.out / f"{spec['id']}.svg"
        target.write_text(render(spec), encoding="utf-8")
        print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
