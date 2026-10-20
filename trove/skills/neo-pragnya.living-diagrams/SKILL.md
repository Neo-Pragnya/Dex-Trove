---
name: living-diagrams
description: "Make diagrams and hero visuals alive: a constellation/orbit plexus canvas (nodes ride orbits around a glowing core, drift freely and are pulled back by springs, link to neighbours, react to the cursor), hover effects for any SVG diagram including rendered Mermaid (hover a node and its neighbours light up, edges flow with dashes, pulses travel along the connections, everything else dims), and animated terminal walkthroughs that type real commands, print real output and tick off a step rail in sync, as one self-contained CSS-animated SVG that plays on GitHub, docs sites and slides. Use whenever someone wants animated or interactive diagrams, graph or network hover effects, a constellation or plexus or orbit hero, connected-node highlighting, to animate a flow or architecture diagram, to show how CLI commands work with an animated terminal or SVG, to turn infographics or slides into animated flows, or wants docs to feel alive, even if they don't say skill or animation."
---

# Living diagrams

Three dependency-free pieces that make diagrams move with meaning:

| Piece | What it does | Where it shines |
| --- | --- | --- |
| `assets/plexus.js` | `<canvas data-plexus="orbits">`: agents ride tilted orbits around a glowing core. They drift off their path and a spring, not a wall, brings them back. Nearby nodes link into a plexus, the cursor attracts and lights links, and a click sends a pulse ring. `data-plexus="web"` gives a free-floating plexus. | heroes, section breaks, "how it connects" moments |
| `assets/diagram-fx.js` + `.css` | Hover a node in any SVG diagram: its edges light up and flow in the direction of travel, pulses run along them, neighbours stay bright and the rest dims. Click pins the focus; Escape releases it. A soft ambient pulse keeps the diagram breathing. Edges are matched to nodes **by geometry**, so it works on rendered Mermaid flowcharts and subgraphs with no ids or conventions. | docs diagrams, architecture maps, dependency graphs |
| `scripts/term_flow.py` | A spec of commands and their **real output** becomes one SVG: a terminal types each command, prints the output, scrolls, and a step rail lights up and ticks off in sync. It uses pure CSS keyframes, so it animates in a GitHub README `<img>`. With *reduce motion*, viewers see the finished session. | READMEs, getting-started guides, release notes, slides |

Pair with the `marvellous-aws-architecture-docs` skill for numbered concept flows, where packets travel arrows and a
legend tells the story. Pair with `interactive-web-motion` for text and shape effects, and with `astro-docs-site` for
the docs site that hosts them all.

## Workflow

1. **Find the story before the effect.** What should a reader understand after watching? A hero plexus says
   "connected, alive, governed". A hover graph answers "what does this touch?". A walkthrough answers "what happens
   when I run it?". Pick only the pieces that answer a real question.
2. **Walkthroughs: capture real output first.** Run the commands in a scratch project with `NO_COLOR=1 COLUMNS=100`.
   Paste the output into a spec (JSON, or a Python file with `SPECS = [...]`). Condense big tables to field/value
   lines and make paths project-relative, but never invent results: a walkthrough is documentation. Mark narration
   with `#`. Commands that don't exist, or outputs you didn't see, must not appear. If an infographic shows commands
   that differ from the real CLI, use the real ones.
3. **Render:** `python scripts/term_flow.py spec.py --out docs/assets/flows`. Long commands wrap with `\`
   continuations. Columns and indentation are kept (spaces become NBSP). Use themes `night` (dark celestial) or
   `paper` (light pastel), or override any colour in `theme`.
4. **Flows from infographics:** read the image, list the stages and what moves between them (artifacts, decisions,
   failures), then write a concept-card spec for `marvellous-aws-architecture-docs`. Number the steps in the order
   things happen, colour failure paths red and dashed, and give each flow a short `packet` label. Re-lay anything
   where arrows overlap or cut through cards. Snake long pipelines into two rows and route loops below the cards with
   `via`.
5. **Hover graphs:** load `diagram-fx.css/js` once per page. Static SVGs need `data-diagram-fx` on the `<svg>`. For
   Mermaid, dispatch `diagram:rendered` (with `detail.svg`) after each render; the `astro-docs-site` template already
   does. Theme with `svg.dfx { --fx-hot: <accent>; }`.
6. **Heroes:** `<canvas data-plexus="orbits" data-colors="#f0cf7a,#bcd0ff" data-core="#ffecb4">` inside a
   `position:relative` container with `position:absolute; inset:0` on the canvas. Mask it away from text, for example
   `mask-image: linear-gradient(100deg, transparent 0 46%, #000 72%)`.
7. **Verify in real time:** `node scripts/cdp_check.mjs <url> out.png 1400 900 '[{"wait":1500},{"moveTo":"g.node","dx":0.5},{"wait":400}]'`.
   Look at the screenshots: lit edges, pulses, typed lines and ticked steps. Headless `--screenshot` with
   `--virtual-time-budget` hardly runs `requestAnimationFrame`, so canvases and hovers look frozen there. Use the CDP
   driver.

## Design rules

- **Motion carries meaning.** Pulses travel in the direction data or control flows. Dashed red means failure or
  blocked. Gold or accent means the focus. Never animate decoration that contradicts the flow.
- **Quiet by default, vivid on intent.** Ambient pulses are small and slow. The full effect comes on hover or focus.
- **Accessible.** Nodes become focusable. Effects respond to keyboard focus as well as the pointer. Reduced motion
  keeps highlighting but drops moving pulses, and walkthroughs show their final frame. Every SVG gets a title and a
  description listing its commands.
- **Honest.** Walkthrough output is real and flows match the actual system. When the product changes, regenerate
  from the spec rather than editing SVG by hand.

## Files

| Path | What |
| --- | --- |
| `assets/plexus.js` | orbit/web constellation canvas (`window.Plexus.init(canvas)`, auto-inits `canvas[data-plexus]`) |
| `assets/diagram-fx.js`, `assets/diagram-fx.css` | hover graph effects (`window.DiagramFX.enhance(svg, opts)`, `auto()`) |
| `scripts/term_flow.py` | terminal walkthrough → animated SVG (stdlib only) |
| `scripts/cdp_check.mjs` | real-time headless Chrome driver for verifying animations (Node 22+, `CHROME=` to override the path) |
| `assets/examples/hello_walkthrough.json` | minimal walkthrough spec to start from |
| `assets/examples/ananke_walkthroughs.py` | three real walkthroughs (quickstart, registry + Dex Trove, governance) |
| `references/recipes.md` | recipes: Mermaid wiring, infographic → flow checklist, theming, troubleshooting |
