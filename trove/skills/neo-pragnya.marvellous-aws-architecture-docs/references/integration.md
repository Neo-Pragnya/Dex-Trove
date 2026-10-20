# Integration: notebooks, decks, READMEs, docs sites

## Jupyter notebooks (teaching or walkthrough notebooks)

* **Opening section**: the complete animated diagram (`svg/<id>.svg`). Introduce it as the map you'll build together,
  and point at the numbered legend.
* **Each section opener**: the matching stage map, with one line explaining the colour key:
  ```markdown
  > 🗺️ **On the map:** pink = what we add in this part · solid = already built · faded = still to come.
  ![map so far](diagrams/svg/<id>-stage-04.svg)
  ```
  For a self-contained notebook, embed the SVG as a base64 `<img src="data:image/svg+xml;base64,…">`; the SMIL/CSS
  animation still runs (packets, pings, caption). Each stage map is about 80 KB; a concept diagram 25-65 KB.
* Each loop lasts `flows × step` seconds (default 2.4 s per step), so 26 flows take about a minute. Split very long
  stories into zoom-ins rather than slowing down the step.
* **Zoom-ins** go next to the section that implements that detail (agent loop, deployment, teardown).
* Keep the specs next to the code (`diagrams/arch_specs.py`) and rebuild them in the same step as the notebook, so
  the pictures never drift from the system.

## HTML slide decks

* Include `archlib.ARCHVIZ_CSS` in the page `<style>` and `archlib.ARCHVIZ_JS` after your deck script (it initialises
  every `.archviz` on the page).
* Use one **interactive** slide (`archlib.interactive_html(spec, "archmain")`) for "the whole system in one picture":
  play the flow live, then click the stage chips to recap the journey.
* Open each chapter with a static stage map (`<img>` of `<id>-stage-NN.svg`) titled "Our map so far: …".
* Each `uid` must be unique on a page. The widget's inline SVG prefixes all its ids with that uid.
* Inside hidden slides, prefer `<img>` stage maps; one inline widget per deck is plenty.
* Live SVGs are wide (they carry their own legend), so give them the full slide width: in CSS grids,
  `figure.diagram{grid-column:1/-1}`.

## READMEs and docs sites

* Commit `svg/<id>.svg` and reference it as an image. GitHub renders the SVG, though it may not run its animation.
  Link the `index.html` page (GitHub Pages, S3 static site or any static host) for the interactive version.
* `index.html` is self-contained (icons and scripts inline), so you can attach it to a wiki or email it.

## draw.io hand-off

`drawio/<id>.drawio` opens in app.diagrams.net and the desktop app. Common AWS services use draw.io's native
`mxgraph.aws4.*` shapes; others are embedded images. Numbers are separate circles. Treat draw.io edits as a fork:
the spec stays the source of truth, so port meaningful changes back to the spec.

## Keeping it honest

* Step text describes what actually happens, verified against the code or IaC.
* Use stage maps for "what exists after step N of the story" and `deleted_at` + `teardown_stage` for clean-up stories.
* If a component is optional or only exists in one profile, say so in its `sub` ("P1 only", "opt-in").
