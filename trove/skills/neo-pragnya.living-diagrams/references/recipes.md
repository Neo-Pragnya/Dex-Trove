# Recipes

## Wire diagram-fx into a docs site that renders Mermaid in the browser

```html
<link rel="stylesheet" href="/diagram-fx/diagram-fx.css" />
<script src="/diagram-fx/diagram-fx.js" defer></script>
```

After each `mermaid.render(...)`, put the SVG into the page and announce it:

```js
figure.innerHTML = svg;
figure.dispatchEvent(new CustomEvent("diagram:rendered", { bubbles: true, detail: { svg: figure.querySelector("svg") } }));
```

Re-renders (for example after a light/dark toggle) should announce again. `enhance()` ignores an SVG it has already
enhanced and builds fresh state for a new one. Sequence diagrams have no node groups, so they're left alone.

Static SVG (hand-made or exported): mark nodes and edges, then opt in.

```html
<svg data-diagram-fx> … <g data-node>…</g> … <path data-fx-edge d="…"/> … </svg>
```

Path direction matters: pulses travel from the path's start to its end.

## Theming

```css
svg.dfx { --fx-hot: #d4a541; --fx-dim: 0.2; }        /* lit edges and pulses; opacity of the rest */
canvas[data-plexus] { position: absolute; inset: 0; } /* fill the hero */
```

`plexus.js` takes colours from `data-colors` (first = accent) and `data-core`. term_flow themes: `night`, `paper`, or
override keys (`bg panel bar ink muted accent accent2 ok warn err card card_on line title`).

## From an infographic to an animated flow (checklist)

1. List the stages exactly as the image shows them, and the artifact each produces (spec.md, plan.md, evidence).
2. Decide what *moves*: the artifact, a decision, a failure. Those become `packet` labels.
3. Order the steps the way time runs. Number loops last and draw them dashed (for example "spec drift →
   regenerate").
4. Snake more than 5 stages into two rows. Loops route below with `via`, and fan-outs get `badge_at` 0.7–0.8 so
   badges don't stack.
5. Render, screenshot, and fix any arrow that overlaps another or crosses a card. Iterate two or three times.
6. Put the animated SVG next to the static infographic (the image gives the overview, the animation gives the
   sequence). Link both from a "See it in action" page.

## Walkthrough spec tips

- `rows` sets the visible terminal height; it scrolls smoothly once full.
- `pause` (seconds) after an entry gives readers time on important output; the default is 0.9.
- Put two runs of the same command in a row to tell a fix story: blocked, then pass.
- `step` maps a command to a rail card. Several commands can share one step; it ticks when the last one finishes.
- Keep it to 4–7 commands. Split longer stories into several walkthroughs.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Hover does nothing on a Mermaid diagram | `diagram:rendered` never fired, or diagram-fx loaded after render without `auto()` | dispatch the event; or call `DiagramFX.auto()` after rendering |
| Only some edges light up | edges end on subgraph (cluster) borders | include `g.cluster` in `nodes` (default), or raise the 40 px snap distance |
| Walkthrough columns collapse | spaces were normalised | term_flow keeps lines that fit verbatim; don't pre-wrap lines yourself |
| Canvas looks frozen in screenshots | virtual-time headless Chrome barely runs frames | use `scripts/cdp_check.mjs` |
| Shapes or paths explode into huge wedges for a frame | an animation used an unclamped negative progress `t` (a rAF timestamp can precede `performance.now()`) | clamp `t` to [0, 1] before easing |
