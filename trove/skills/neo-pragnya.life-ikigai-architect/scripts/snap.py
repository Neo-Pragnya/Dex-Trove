#!/usr/bin/env python3
"""Screenshot slides of a built deck with headless Chrome (for visual QA).

    python snap.py deck.html --slides 1 5 9 --out shots/          # desktop 1440x900
    python snap.py deck.html --slides 9 --theme dark --size 390x844  # phone, dark theme
    python snap.py deck.html --slides 11 --sel center              # preselect a venn/wheel/petal region
    python snap.py deck.html --all --out shots/                    # every slide

Slides open at deck.html?static#N. `?static` is the deck's snapshot mode: no animation, every fragment
revealed, roadmaps fully lit, score bars full. Headless "virtual time" does not advance CSS animations, so
never verify animated frames that way. Use --offline when the machine has no network (blocks Google Fonts
so the page doesn't wait on them; fallback fonts are used).
"""
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "", shutil.which("chromium") or "", shutil.which("chromium-browser") or "",
]


def chrome():
    for c in [os.environ.get("CHROME", "")] + CANDIDATES:
        if c and os.path.exists(c):
            return c
    sys.exit("Chrome/Chromium not found; set CHROME=/path/to/chrome")


def shoot(exe, url, png, w, h, offline, limit=60):
    with tempfile.TemporaryDirectory() as prof:
        # headless Chrome won't make a window narrower than ~500px, so phone sizes render inside an iframe
        if int(w) < 520:
            frame = pathlib.Path(prof) / "frame.html"
            frame.write_text(f'<body style="margin:0;background:#666"><iframe src="{url}" width="{w}" height="{h}" '
                             f'style="border:0;display:block"></iframe></body>', encoding="utf-8")
            url, w = frame.as_uri(), "520"
        cmd = [exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
               f"--window-size={w},{h}", f"--screenshot={png}", "--enable-logging=stderr", "--v=0",
               "--allow-file-access-from-files"]
        if offline:
            cmd.append("--host-resolver-rules=MAP fonts.googleapis.com 127.0.0.1, MAP fonts.gstatic.com 127.0.0.1")
        cmd.append(url)
        if png.exists():
            png.unlink()
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        t0 = time.time()
        while time.time() - t0 < limit and not (png.exists() and png.stat().st_size > 0):
            time.sleep(0.4)
        time.sleep(0.3)
        p.kill()
        err = p.stderr.read() if p.stderr else ""
        return png.exists(), [l for l in err.splitlines() if "CONSOLE" in l]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--slides", nargs="*", type=int, default=[1])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default="shots")
    ap.add_argument("--size", default="1440x900")
    ap.add_argument("--theme", choices=["light", "dark"], help="force the deck theme (default: follow the OS)")
    ap.add_argument("--sel", help="preselect a region key on interactive slides (venn: love, passion, center...; others: 0,1,2...)")
    ap.add_argument("--offline", action="store_true", help="block Google Fonts (no network available)")
    a = ap.parse_args()
    deck = pathlib.Path(a.deck).resolve()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    n = len(re.findall(r'<section class="slide ', deck.read_text(encoding="utf-8")))
    slides = list(range(1, n + 1)) if a.all else a.slides
    w, h = a.size.split("x")
    exe = chrome()
    problems = []
    for k in slides:
        tag = f"{'-' + a.theme if a.theme else ''}{'-' + a.sel if a.sel else ''}-{a.size}"
        png = out / f"slide-{k:02d}{tag}.png"
        q = "?static" + (f"&sel={a.sel}" if a.sel else "") + (f"&theme={a.theme}" if a.theme else "")
        ok, logs = shoot(exe, f"{deck.as_uri()}{q}#{k}", png, w, h, a.offline)
        problems += [f"slide {k}: {l.strip()[:300]}" for l in logs]  # the deck logs nothing; any console line is news
        print(f"slide {k:2d} -> {png if ok else 'FAILED'}")
        if not ok:
            problems.append(f"slide {k}: no screenshot produced")
    if problems:
        print("\nProblems:", *problems, sep="\n  ")
        sys.exit(1)
    print(f"{len(slides)} screenshot(s), no console output.")


if __name__ == "__main__":
    main()
