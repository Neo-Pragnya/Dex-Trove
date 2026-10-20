# Spec reference

A spec file is plain Python that imports from `archlib` and defines `SPECS = [Spec, ...]` (the CLI also accepts `ALL`).
`build_arch.py` puts `scripts/` on the path, so `from archlib import Flow, Group, Node, Spec, Stage` just works.

```python
from archlib import Flow, Group, Node, Spec, Stage

STAGES = [Stage(0, "Static web app", "Release 1", "React app on S3 behind CloudFront"), ...]

SYSTEM = Spec(
    id="rag-chatbot",                       # file names: svg/rag-chatbot.svg, drawio/rag-chatbot.drawio
    title="Serverless RAG chatbot — answers grounded in your own documents",
    subtitle="One sentence: what the picture shows and the key design choice.",
    cols=8.6, rows=4.6,                     # minimum grid size; the canvas grows automatically to fit
    stages=STAGES,                          # optional; enables stage maps and the "Build it up" chips
    teardown_stage=None,                    # optional; from this stage on, nodes with deleted_at are crossed out
    groups=[...], nodes=[...], flows=[...],
)
SPECS = [SYSTEM]
```

## Grid

* `x` = column, `y` = row; each cell is 168 × 128 px. Fractions are fine (`5.35`, `2.68`), and negative rows are fine
  too: the header moves down automatically.
* A node's `x, y` is its icon centre. Its label sits under the icon (up to 2 lines of title + 2 of subtitle), so leave
  about 0.55 rows under any icon free of lines.
* A group spans node centres `x0..x1 × y0..y1`; the rectangle extends about half a cell beyond them. For nested
  groups, give the inner one fractional coordinates about 0.15 inside the outer.

## `Node(id, icon, title, sub="", x, y, stage=0, deleted_at=None)`

| Field | Meaning |
|---|---|
| `icon` | key from `assets/icons/CATALOG.md` (e.g. `bedrock`, `eks`, `api-gateway`, `pod`), or `None` for a text box (your own code/modules). Unknown keys become text boxes with a warning |
| `title` | service or component name ("Amazon S3", "Agent pod") |
| `sub` | its role, shown in italics ("data · artifacts", "FastAPI + same package") |
| `stage` | the stage that introduces it (used by stage maps and the widget) |
| `deleted_at` | the stage at which teardown removes it (with `Spec.teardown_stage`) |
| `body` | list of lines → the node becomes a **card**: coloured header (icon + title), body lines below (wrapped), `sub` as a corner tag |
| `color` | card header/border colour, or the border of a text box (e.g. red for the "prediction point") |
| `w`, `h` | width/height in grid cells for cards and text boxes (card default 1.55 wide, height fits the text) |

Cards are larger than icons: space their centres by about `w + 0.25` cells horizontally, and check `y` against their
height (about 0.45 rows for 1 body line, 0.75 for 4).

## `Group(id, title, x0, y0, x1, y1, style="logic", stage=0, icon=None)`

| `style` | Looks like | Use for |
|---|---|---|
| `cloud` | solid dark border | AWS Cloud / your account |
| `region` | dashed teal | a Region or a managed environment (SageMaker Studio) |
| `vpc` | solid purple | VPC |
| `subnet` | green fill | public/private subnet |
| `cluster` | dashed orange, light fill | EKS/ECS cluster, node group, Auto Scaling group |
| `logic` | dashed grey | logical grouping ("Data ingestion pipeline", "Safety net") |

`icon` puts a small icon in the title (e.g. `vpc`, `ec2`, `s3`, `sagemaker`).

## `Flow(n, src, dst, text, label="", stage=0, sp=None, dp=None, mid=0.5, bidir=False, dashed=False, badge_at=0.22, via=None, so=0, do=0)`

| Field | Meaning |
|---|---|
| `n` | step number; flows must be numbered 1..N in list order |
| `text` | the legend sentence: what happens at this step, in plain words |
| `label` | short italic text on the arrow ("S3 event", "SigV4", "/chat") |
| `sp`, `dp` | source and destination sides: `l r t b`. Auto: horizontal if \|dx\| ≥ \|dy\|, else vertical |
| routing | `l/r → l/r`: H-V-H (elbow at `via` column or `mid` fraction) · `t/b → t/b`: V-H-V (elbow at `via` row) · mixed: one bend |
| `via` | absolute grid x (for left/right ports) or y (for top/bottom ports) of the elbow; use it to route through gaps |
| `so`, `do` | pixel offset of the source/destination port along its side; separates arrows sharing a side |
| `badge_at` | where the number badge sits along the path (0..1); move it off labels |
| `dashed` | safety-net, async or failure paths |
| `bidir` | arrowheads both ends (request/response) |
| `packet` | short label riding on the moving dot in the live SVG ("SQL", "sha256", "ABSENT"); keep it under 12 characters |
| `color` | colour the line, arrowhead and packet by meaning (red = forbidden / failure path, green = the safe route) |
| `stage` | stage that introduces the flow |

## `Stage(k, title, parts, blurb)`

`k` are integers from 0. `parts` is the chip label ("Part 16", "Release 2", "Sprint 3"); `title` is a short name;
`blurb` is what appears ("CodeBuild → ECR → EKS pod…"). The build checks that every stage used by a node or flow is
declared.

## Python API (for custom pipelines)

```python
import archlib
svg = archlib.render_svg(spec)                                   # live complete diagram (packets, pings, caption bar)
svg = archlib.render_svg(spec, step=3.0)                         # slower: seconds per numbered step (default 2.4)
svg = archlib.render_svg(spec, animate=False)                    # a still image
svg = archlib.render_svg(spec, stage=3, title="…", subtitle="…") # map so far at stage 3
xml = archlib.render_drawio(spec)
html_widget = archlib.interactive_html(spec, uid="arch1", start_stage=None)
css, js = archlib.ARCHVIZ_CSS, archlib.ARCHVIZ_JS                # include once per page
```

Icons resolve from `$ARCHLIB_ICONS`, then `scripts/icons`, then `assets/icons`. Copy `assets/icons` into a project
(e.g. `diagrams/icons`) and copy `archlib.py` beside it when you want the project to build without the skill.
