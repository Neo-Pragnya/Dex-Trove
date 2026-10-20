# Layout playbook

Good AWS diagrams read like a sentence: left to right, top to bottom, few crossings, every number near the arrow it
names. The engine computes pixels; your job is to place nodes so most flows connect neighbours, and to steer the few
long flows through empty space.

## 1. Plan the grid before typing coordinates

1. **Columns** follow the request: actors (col 0, outside the cloud) → edge and front end → APIs and compute → data and
   AI services → operations. **Rows** separate planes: the control plane and build pipeline on top, the request path in
   the middle, data and ingestion below, safety nets and observability at the bottom.
2. Sketch it as a table of `(x, y) → node` first. Leave **empty gap rows** (e.g. y = 1.6, 3.7) where long flows can run.
3. Put each group's members in consecutive cells. A group needs about 0.47 rows above its first node for its title.

## 2. Route long flows through gaps

* `sp="t", dp="t", via=-0.6`: up and over the top of everything (a "top lane").
* `sp="b", dp="b", via=3.8`: under a row (a "bottom lane").
* `sp="r", dp="l", via=9.7`: down a vertical lane to the right of a group.
* Lanes must not sit exactly on a group's border or title (about 0.4–0.55 rows above a group's first node). Keep
  0.1–0.15 rows between parallel lanes.
* Two flows leaving the same side: give them different `so` (e.g. -16 and +16). The same goes for two flows arriving
  at one side (`do`).
* A flow between neighbours in the same row or column needs no hints at all.

## 3. Fix what the screenshot shows

| Symptom | Fix |
|---|---|
| Arrow runs through an icon | change `sp/dp` so it leaves upward/downward, or add `via` to use a gap |
| Line crosses a group title | move the lane (`via`) or widen/shift the group (e.g. start `x0` 0.5 earlier) |
| Badge sits on a label | `badge_at=.6` … `.85` |
| Several badges stacked at one port | separate with `so`, and put badges far along each path (`badge_at=.85`) |
| Label wraps into a third line | shorten `sub` ("Nova Pro + 4 fallbacks") |
| Group runs into the legend | nothing: the canvas sizes itself. If a node's label is clipped, increase `rows`/`cols` slightly |
| Arrowheads hidden behind text boxes | ports are box-aware; if you still see it, give the flow explicit sides |

## 4. Verify (always look at the picture)

```bash
python scripts/build_arch.py specs.py --out /tmp/arch
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars \
   --window-size=2400,1200 --screenshot=/tmp/arch.png "file:///tmp/arch/svg/<id>.svg"
# a stage view, and the interactive page preset to a stage:
#   file:///tmp/arch/svg/<id>-stage-03.svg      file:///tmp/arch/index.html?archstage=3
```

**Freeze the animation for a deterministic screenshot.** Headless Chrome's virtual clock advances SMIL but not CSS, and
the frame you get depends on load time. Copy the SVG and insert before `</svg>`:
`<script>var r=document.documentElement;r.pauseAnimations();r.setCurrentTime(9.0);</script>` - at 9 s with the
default 2.4 s step you see step 4: caption, orange badge, orange legend number and the packet all on the same step.
Check two or three times per diagram, looking for packets or pills that cover labels.

Use `--force-device-scale-factor=2` with a small window to inspect details (icon crispness, badge overlaps). On Linux,
use `google-chrome` or `chromium` with the same flags.

## 5. When to split

Past about 30 flows or about 25 nodes, the legend gets long and the arrows tangle. Keep one **overview** (every
service, the main 15–25 steps) and add **zoom-ins** for detail (an agent's internal loop, a deployment path, a
teardown/safety net), each with its own numbering from 1.
