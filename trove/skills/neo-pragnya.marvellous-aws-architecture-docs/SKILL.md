---
name: marvellous-aws-architecture-docs
description: "Marvellous AWS Architectures Docs: build AWS-reference-style architecture diagrams as code (official AWS icons, account/VPC/cluster boundaries, numbered steps with a legend) and publish animated SVGs, stage-by-stage map-so-far views, editable draw.io files and an interactive HTML docs page (play the flow, build the system up stage by stage). Use whenever the user wants an architecture, reference-architecture, data-flow, request-flow or deployment diagram, or architecture docs, for anything on AWS (Bedrock, SageMaker, Lambda, EKS/ECS, API Gateway, S3, DynamoDB, RAG or agent systems, data or ML pipelines). This includes requests like draw our architecture, make it look like AWS reference architectures, animate or number the flow, show how it is built up part by part, a diagram for slides, notebook, README or docs, or redoing hand-drawn or draw.io diagrams, even if they do not say skill or architecture as code. Also concept diagrams (cards + live flows)."
---

# Marvellous AWS Architectures Docs

Turn a system into **AWS-reference-style architecture diagrams that are generated from a short spec**, not hand-placed:
official AWS icons inside account / VPC / cluster boundaries, numbered flows with a numbered legend, an animation that
walks the flow, "map so far" views that build the system up stage by stage, editable draw.io output, and one shareable
interactive docs page.

Why code instead of drawing: coordinates placed by hand don't scale, drift from the real system, and can't be
re-rendered for each stage of a story. A spec is reviewable, diffable and regenerates every artefact consistently.

## What you produce

| Output | File | Use it for |
|---|---|---|
| Complete diagram, **live** | `svg/<id>.svg` | README, notebook, slides. Each numbered flow plays in turn: a glowing packet (optionally labelled, e.g. "SQL", "sha256") travels the arrow, the destination pings, a caption bar narrates "▶ NOW 3 · …" and a progress bar runs. SMIL + CSS on one clock, so it animates even as an `<img>` |
| "Map so far" per stage | `svg/<id>-stage-NN.svg` | Opening each section/notebook part/chapter: new = pink glow + marching ants + looping packets, built = solid, future = faded, torn down = crossed |
| Editable diagram | `drawio/<id>.drawio` | Hand-off to people who edit in draw.io (native `mxgraph.aws4.*` shapes; image fallback for others) |
| Interactive docs page | `index.html` | Sharing: ▶ play the flow (a dot travels each arrow), ‹ › step, click a legend line to jump, stage chips to build it up, step table, downloads |
| Deck/web widget | `archlib.interactive_html(spec, uid)` + `ARCHVIZ_CSS` + `ARCHVIZ_JS` | Embedding the interactive diagram in your own HTML |

## Workflow

1. **Understand the system before drawing.** Read the code/IaC/README (or ask) for: actors, AWS services and the
   boundaries they sit in (account, Region, VPC, subnets, cluster), and the 8-30 steps of the main flows in the order
   they happen. If the user wants a story ("build it up part by part"), also decide the **stages** (sprints, releases,
   notebook parts, chapters) and which stage introduces each node and flow. Getting the steps right matters more than
   the layout; a pretty diagram with a wrong flow is worse than none.
2. **Write the spec** (`arch_specs.py`, defines `SPECS = [...]`). Start from `assets/examples/serverless_rag_chatbot.py`
   (small) or `assets/examples/wwi_data_science_agent.py` (large, with stages, teardown and three zoom-ins).
   Field reference: `references/spec-reference.md`. Icon keys: `assets/icons/CATALOG.md` (126 icons).
3. **Lay out on a grid** with the playbook in `references/layout-playbook.md`. The essentials:
   - Flow left → right; actors in column 0 outside the cloud boundary.
   - Put things that talk to each other next to each other.
   - Route long flows through the gaps between rows or columns with `via`, and separate arrows that share a side with `so`/`do`.
4. **Build:** `python scripts/build_arch.py arch_specs.py --out docs/architecture --title "…" --intro "…"`.
   The build fails on dangling flow endpoints, duplicate ids, numbers that aren't 1..N, and stages that aren't declared.
5. **Look at it**, then fix it. Render a screenshot (see `references/layout-playbook.md` §Verify; headless Chrome works)
   and fix every arrow that crosses an icon or label, every badge sitting on text, and every lane that runs through a
   group title. Iterate two or three times; it's quick. Check one stage view and the `index.html` too
   (`index.html?archstage=K` presets a stage, which is handy for screenshots).
6. **Integrate** where the user needs it: notebook, slides, README, docs site. See `references/integration.md`:
   - full map once, then a stage map at each section opener;
   - zoom-in diagrams next to the detailed sections;
   - one interactive slide.
7. **Report** what you built: the files, and how to rebuild and edit (spec → build). Note any icon you substituted.

## Style rules that make it look like AWS reference architectures

- **Boundaries tell the security story**: AWS Cloud / account → Region → VPC → subnet → cluster/node group, plus dashed
  *logical* groups ("Data ingestion pipeline"). Put a group's icon in its title (VPC, S3, EC2 node group…).
- **Numbers are the order things happen**, not importance. One sentence per step in the legend, phrased as what
  happens ("An S3 event triggers ingestion…"). 8-30 steps per diagram; split into zoom-ins beyond that.
- **Dashed arrows** are safety-net, asynchronous or failure paths; `bidir=True` for request/response pairs.
- **Real service names** under the icon, the role in italics ("Amazon S3" / *data · artifacts*). Text boxes
  (`icon=None`) are for your own code (graph nodes, modules); AWS services always get their official icon.
- **Never imply something you don't build**: a NAT gateway, load balancer or public endpoint should appear only if it
  exists. If the design deliberately avoids one, say so in a group title ("no NAT gateway").
- Keep it honest about models and data: label models by family/fallback order, not marketing names.

## Concept diagrams: cards + icons + live flows

Not every picture is a deployment. For an *idea* (a data model and its safe joins, a lifecycle with gates, a decision
flow, memory vs state), use **cards**: `Node(..., body=["fact", "fact"], color="#B4322A", w=2.1)` gives a coloured
header (with the icon, if any), the facts that matter as body lines, and an optional `sub` tag in the corner. Mix cards
with real AWS icons where a service is involved, colour flows by meaning (`Flow(color=…)`: red = forbidden/failure,
green = the safe route) and give each flow a `packet` label so the moving dot says what travels ("rows", "token",
"ABSENT"). Each legend line should read as one sentence of the story; the caption bar replays them in order.
Start from `assets/examples/concept_cards.py` (semantic layer, leakage timeline, cost gates).

## Bundled resources

| Path | What |
|---|---|
| `scripts/archlib.py` | The engine: data model (`Spec`, `Node`, `Group`, `Flow`, `Stage`), layout/routing, SVG, draw.io, interactive widget |
| `scripts/build_arch.py` | CLI: spec file → `svg/`, stage maps, `drawio/`, `index.html` docs page |
| `scripts/fetch_icons.py` | Rebuild or extend the icon set from the official AWS Architecture Icons (`--add key=path`) |
| `assets/icons/` | 126 icons at 64 px (AWS services, Kubernetes, common tech), `CATALOG.md`, `SOURCE.md` |
| `assets/examples/serverless_rag_chatbot.py` | Small example with four release stages |
| `assets/examples/wwi_data_science_agent.py` | Large example: 26 flows, 12 stages, teardown, 3 zoom-ins |
| `assets/examples/concept_cards.py` | Concept diagrams: cards, coloured flows, packet labels |
| `references/spec-reference.md` | Every field, with defaults and when to use it |
| `references/layout-playbook.md` | Grid layout, routing through gaps, overlap fixes, verification |
| `references/integration.md` | Notebook stage maps, slide decks, README/docs, draw.io hand-off |

Requirements: Python 3.10+ (standard library only for building). Pillow is needed only for `fetch_icons.py`; headless
Chrome or any browser for checking the result.
