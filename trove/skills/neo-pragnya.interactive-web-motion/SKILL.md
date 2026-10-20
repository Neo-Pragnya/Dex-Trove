---
name: interactive-web-motion
description: "Add playful, modern, accessible interactions to a website or GitHub Pages docs site: SVG shapes that morph on hover (circle → star → flower → blob), a cursor-reactive hero field of pastel shapes, rotating words, letter hover waves (colour, weight, typeface), particle text that diffuses from the cursor, blur-in scroll reveals, count-up stats, magnetic buttons, tilt + spotlight cards, marching-ants borders, marquees, drifting aurora backgrounds and film grain, from one dependency-free motion-kit.js + motion-kit.css driven by data attributes. Use whenever someone wants a site to feel alive, modern, fun or less static, wants hover animations, morphing SVGs or effects like graphify.com, Stripe or Linear, asks for an animated hero, landing page polish, micro-interactions, scroll animations or a pastel redesign, or wants to upgrade Astro/MkDocs/plain-HTML docs or a GitHub Pages site visually, even if they don't name a library."
---

# Interactive Web Motion

Give a static site a living, tactile feel without a framework or a bundle-size hit. One small script
(`assets/motion-kit.js`, ~12 KB unminified, no dependencies) and one stylesheet (`assets/motion-kit.css`) power
everything through **data attributes**, so the same kit drops into Astro, MkDocs, Hugo, Jekyll or hand-written HTML.

Open `assets/gallery.html` in a browser to see and feel every effect before choosing.

## The toolkit

| Effect | Markup | Use it for |
| --- | --- | --- |
| Morphing shape | `<svg viewBox="0 0 100 100" data-morph="circle>star"></svg>` | icons on cards, nav, buttons; the shape changes when its link/button is hovered or focused |
| Cycling shape | `data-morph="circle star hex flower"` (+ `data-morph-auto="2400"`) | logos, empty states, playful accents |
| Shape field | `<canvas data-field="36"></canvas>` inside a `position:relative` hero | hero backgrounds: pastel shapes drift, flee the pointer and morph when it comes near |
| Rotating word | `<span data-words="agents\|teams\|docs">agents</span>` | the word itself changes: letters tip out and the next word rises in, while the slot's width glides (`data-colors` paints a gradient) |
| Letter wave | `<h2 data-letters>Title</h2>` | headings and CTAs: letters near the pointer lift, gain weight and shift to `--mk-hot`; set `--mk-alt-font` to swap typeface on the hottest letters |
| Particle text | `<span data-particles="#c1,#c2">Title</span>` | one hero line: text made of particles that assemble, diffuse away from the cursor and spring back (single line; wrapped text falls back to normal) |
| Letter rise | `<h1 data-rise>Title</h1>` | quiet entrance: letters rise and un-blur, staggered, when revealed. `data-scramble` is now an alias (random-glyph scrambling read as glitchy, so it was retired) |
| Scroll reveal | `<div data-reveal style="--d:.1s">` | sections and cards: fade + un-blur + rise, staggered by `--d` |
| Count-up | `<span data-countup>968</span>` | stats |
| Magnetic | `<a data-magnetic>` | primary buttons |
| Tilt + spotlight | `<div data-tilt>` | cards (sets `--mx/--my` for a light that follows the pointer) |
| Marching ants | `class="ants"` (+ `--mk-ants: colour`) | dashed animated outline on hover/focus, graphify-style |
| Marquee | `<div data-marquee><div>…</div><div aria-hidden="true">…same…</div></div>` | logos, sources, tags |
| Aurora | `<div class="mk-aurora" style="--mk-aurora-a:…;--mk-aurora-b:…">` | soft drifting colour behind a hero |
| Grain | `<body class="mk-grain">` | subtle film texture over flat pastel backgrounds |

Gradient-text headings (`background-clip: text`) can't reach split letters, so give split text its colours with
`data-colors="#a,#b,#c"`. Variable fonts make the letter-wave weight change smooth: load ranges such as
`Inter:wght@100..900`.

Shapes available: `circle square squircle triangle diamond hex octagon star star4 star6 spark flower flower4
flower8 blob blob2 blob3 cloud gear`. Add more with `MotionKit.registerShape(name, theta => radius)`.

## How the morphing works (and why it's smooth)

Every shape is a **radius function r(θ)**, sampled at the same 120 angles and normalised to 0–1. Morphing is
just interpolating 120 numbers. Any shape can become any other with no point-matching problems (the usual
reason SVG path morphing needs heavy libraries like flubber or GSAP MorphSVG). The points are drawn as a closed
Catmull-Rom spline, which gives polygons softly rounded corners: a friendly, modern look. Read
`references/patterns.md` before adding new effects.

## Workflow

1. **Pick a palette and a personality.** Pastels on a warm off-white read as modern and welcoming: crimson-orange
   `#ff7a59`, lemon `#ffd84d`, chartreuse `#b5e655`, turquoise `#46d1c6`, lilac `#a78bfa`, sky `#7cc4ff`, pink
   `#ff8fb1` on `#fffaf0`. Use the saturated colour for shapes, borders and fills. For **text** on pastel
   backgrounds use a darker ink of the same hue (contrast ≥ 4.5:1), never the pastel itself. See
   `references/patterns.md` › Colour.
2. **Install the kit** into the site:
   ```bash
   python scripts/install_motion_kit.py <site-dir>        # Astro: copies to <site>/public/motion-kit/
   python scripts/install_motion_kit.py <dir> --plain     # plain HTML / MkDocs: copies next to your assets
   ```
   Then load it once in the base layout:
   ```html
   <link rel="stylesheet" href="/motion-kit/motion-kit.css" />
   <script src="/motion-kit/motion-kit.js" defer></script>
   ```
   (In Astro, prefix with `import.meta.env.BASE_URL` for GitHub Pages project sites.)
3. **Choose 3–5 effects, not all twelve.** A good default:
   - hero: `mk-aurora` + `canvas[data-field]` + a `data-particles` line + a `data-words` slot
   - every card: a `svg[data-morph]` glyph + `data-reveal`
   - stats: `data-countup`
   - primary CTA: `data-magnetic` + `ants`
4. **Give each content type a shape.** Map categories to shape pairs (rest → hover) and colours, e.g. skill
   `blob>star`, agent `circle>flower`, plugin `hex>spark`. Repeat the same mapping everywhere (cards, chips, page
   headers) so the shapes become a visual language.
5. **Verify** (see below), including reduced motion and a phone-width check.

## Accessibility and performance rules

- Everything honours `prefers-reduced-motion`. Reveals show instantly, morphs jump, the field draws one still
  frame, and marquees and auroras stop. Never bypass this.
- Content is never hidden without JS: the reveal styles only apply after the script adds `mk-ready`.
- Decorative SVG and canvas need `aria-hidden="true"`. Split and particle text keep the real text in a visually hidden `.mk-sr` span, so screen readers and selection get the words, not letters.
- The field pauses when off-screen (IntersectionObserver) and caps device-pixel-ratio at 2.
- Elements visible at load are revealed directly; the observer only handles elements below the fold.
- Keep motion short (≤ 800 ms) and use one easing everywhere (`cubic-bezier(.22,1,.36,1)`).

## Verify

```bash
# 1. Screenshots with frames running (hero field, morph glyphs, reveals)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --hide-scrollbars \
  --virtual-time-budget=4000 --window-size=1400,1800 --screenshot=out.png http://localhost:4321/
# 2. Static mode (what reduced-motion users get, and deterministic for diffs)
…same… "http://localhost:4321/?motion=static"
# 3. Phone width: render the page in a 390px iframe (headless Chrome enforces a ~500px minimum window)
```

- `--dump-dom` produces only **one animation frame**, so to test interaction logic, dispatch events and assert in
  `?motion=static` mode (morphs apply instantly). See `references/verification.md`.
- Check both colour schemes if the site has a theme toggle.

## Files

| Path | What |
| --- | --- |
| `assets/motion-kit.js` | the runtime (auto-inits; `window.MotionKit` API: `init`, `settle`, `registerShape`, `pathFor`, `shapes`) |
| `assets/motion-kit.css` | reveal, ants, marquee, aurora, grain, tilt spotlight, reduced-motion rules |
| `assets/gallery.html` | live demo of every effect, also a visual test |
| `scripts/install_motion_kit.py` | copy the kit into a site |
| `references/patterns.md` | design patterns, colour, shape language, do and don't |
| `references/verification.md` | headless screenshot, static-mode and interaction tests |
