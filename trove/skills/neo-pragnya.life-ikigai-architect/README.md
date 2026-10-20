# Life Ikigai Architect

Turn reflections, journals or a long purpose conversation into a **personal Ikigai, vision, mission, values and
roadmap**, delivered as one self-explanatory, animated HTML presentation. Content lives in a JSON spec; the engine
renders it.

![hero](assets/previews/hero.png)
![interactive Ikigai](assets/previews/venn.png)
![vision to values](assets/previews/vision-mission.png)
![ecosystem with live flows](assets/previews/ecosystem.png)
![roadmap](assets/previews/roadmap.png)

## Quick start

```bash
python scripts/build_deck.py assets/examples/maya_example.json --out /tmp/maya.html
open /tmp/maya.html          # → / Space to advance · M contents · T theme · click the Venn regions
```

Copy `assets/examples/starter.json`, fill it (see `references/reflection-protocol.md` for the questions and
`references/frameworks.md` for how to turn answers into each section), then build your own. Check it with
`python scripts/snap.py your_deck.html --all`.

* 22 slide types: interactive four-circle Ikigai, six-dimension petals, triad, principles wheel, trinity with a
  sustainability ring, vision → mission → pillars → values cascade, ecosystem with animated flows, role cycle, chain,
  layered funding model, roadmaps with a travelling comet, a scoring heatmap you can re-rank, compare, questions,
  image, closing.
* One self-contained HTML file: light/dark, phone layout, print to PDF, keyboard and swipe, `prefers-reduced-motion`.
* Python 3.9+, standard library only. Chrome/Chromium only for screenshots.

Your spec and deck are personal. Keep them in your own folder, not in this skill.
