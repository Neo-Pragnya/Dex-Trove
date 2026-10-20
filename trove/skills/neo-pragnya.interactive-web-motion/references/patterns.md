# Patterns

## Personality first

Decide what the motion should *say* before adding any:

| Personality | Effects | Avoid |
| --- | --- | --- |
| Playful, welcoming (libraries, community, education) | morphing glyphs, shape field, count-up, soft aurora | glitch, harsh flashes |
| Technical, precise (dev tools, infra) | marching ants, scramble, dashed borders, grid backgrounds, wireframes | bouncy easing, blobs |
| Calm, editorial (docs, research, writing) | reveals, subtle tilt, grain, one accent morph | fields, marquees |

Graphify (graphify.com) is a good reference for the *technical* end. It uses dashed "marching" borders, glitch and
tear effects on headings, a floating field of math symbols, a dashed wireframe cube, blur-in reveals and film grain,
all on one `cubic-bezier(.22,1,.36,1)` ease. Borrow the craft (consistent easing, texture, hover feedback on
everything clickable), not the look.

## Colour

Pastel palette on a warm off-white background:

| Name | Strong (shapes, borders) | Soft (fills, chips) | Ink (text on soft) |
| --- | --- | --- | --- |
| crimson-orange | `#ff7a59` | `#ffe3d9` | `#a3361a` |
| lemon | `#ffd84d` | `#fff6c7` | `#7a5a00` |
| chartreuse | `#b5e655` | `#eefbd0` | `#476b00` |
| turquoise | `#46d1c6` | `#d6f6f3` | `#0b6b63` |
| lilac | `#a78bfa` | `#ede6ff` | `#5b3cc4` |
| sky | `#7cc4ff` | `#e0f1ff` | `#1d5f99` |
| pink | `#ff8fb1` | `#ffe4ec` | `#a3224b` |

- Background `#fffaf0`; surfaces `#ffffff`; lines `#efe7d6`; ink `#1f1d2b`; muted `#5b5870`.
- Strong colours are for **non-text** marks. Text uses the ink column: all reach ≥ 4.5:1 on their soft colour and
  on white.
- If you keep a dark theme, make it opt-in (a toggle), and re-tint the pastels slightly brighter.

## Shape language

Give every *category* in the site a rest → hover pair and a colour, and use it consistently:

```text
skill        blob     → star       turquoise
agent        circle   → flower     crimson-orange
instruction  squircle → square     lemon
prompt       triangle → circle     lilac
hook         diamond  → spark      pink
workflow     hex      → blob2      sky
plugin       octagon  → flower8    chartreuse
```

The rest shape is calm and rounded; the hover shape is lively, with more points and a slight spin (the kit adds
0.35 rad). The morph *is* the hover feedback, so you rarely need a separate hover colour change.

## Layout patterns

- **Hero:** `position:relative; overflow:hidden; border-radius:28px` container, `mk-aurora` +
  `canvas[data-field]` behind, content on top (`position:relative; z-index:1`). Keep the headline short (≤ 8
  words) and scramble only the headline.
- **Card grid:** glyph (`svg[data-morph]`, 44–56 px) top-left, title, 2–3 line description, meta chips. Put
  `data-reveal` with an increasing `--d` (0, .05, .1 …, capped at .3 s).
- **Stats band:** `data-countup` numbers in large weight-800 type, with tiny labels.
- **Section headings:** eyebrow (small caps, strong colour), heading, one-line lede.
- **Buttons:** pill shape, ink background, `data-magnetic` + `ants` with a strong colour.

## Don't

- Don't animate layout properties (width, top, left); the kit only uses transform, opacity and filter.
- Don't put `data-field` on more than one element per page.
- Don't scramble long paragraphs, links in prose, or anything a screen reader reads repeatedly.
- Don't auto-morph more than three things on screen at once.
- Don't hide primary content behind hover. Hover adds delight; it never reveals information that touch users
  can't reach.
