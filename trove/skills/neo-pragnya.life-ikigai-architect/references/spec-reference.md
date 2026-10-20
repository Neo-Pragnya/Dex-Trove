# Spec reference

A spec is JSON (or a `.py` file defining `SPEC = {...}`):

```json
{
  "meta": {"title": "Life Ikigai Architecture", "description": "one line", "lang": "en", "fonts": true},
  "chapters": [{"id": "open", "title": "Opening", "icon": "🌅", "blurb": "…", "color": "gold"}],
  "slides": [{"type": "hero", "ch": "open", "title": "…"}]
}
```

- `chapters[].id` is referenced by each slide's `ch`; chapters drive the contents menu, the HUD label and `agenda`.
- `meta.fonts: false` drops the Google Fonts link (fully offline; system serif and sans fallbacks).
- **Inline markdown** in any text field: `**bold**` (in titles: gradient), `*italic*` or `_italic_`, `` `code` ``,
  `\n` line break.
- **Colours** (`color` on cards, nodes, phases…): `love` `good` `need` `paid` `lotus` `indigo` `gold` `acc` `warn`
  `bad` `ok`, or any CSS colour. When omitted, most types cycle through the palette; `cards` uses the accent unless
  `rainbow: true`.

## Fields shared by every slide

| Field | Use |
|---|---|
| `type` | one of the types below (required) |
| `ch` | chapter id |
| `kicker` | small uppercase line above the title: where we are |
| `title` | the headline; put one key phrase in `**bold**` |
| `intro` | a sentence telling a newcomer how to read the slide |
| `summary` | takeaway, rendered as a quote block at the end |
| `note` | small muted footnote |

## Slide types

| Type | Required | Optional fields | Limits / tips |
|---|---|---|---|
| `hero` | `title` | `kicker`, `jp`, `subtitle`, `tagline` | Animated mandala in the Ikigai palette |
| `agenda` | | `skip` (chapter ids) | Auto-built from `chapters`; cards jump to chapters |
| `statement` | | `quote`, `lines[]`, `sanskrit`, `attribution` | Lines reveal one by one |
| `text` | | `paras[]`, `bullets[]`, `quote` | Plain prose slide |
| `cards` | `cards[]` | `columns` (1-5), `tone` (`warn`), `rainbow`; card: `icon,title,body,tag,color,remedy,points[]` | ≤12 cards; `remedy` renders as "→ …" in green |
| `table` | `columns[]`, `rows[[]]` | `highlight[]` (row indices), `compact` | First column bold; scrolls sideways on phones |
| `venn` | `circles{}` | `overlaps{}`, `lenses{}`, `center{}`, `how` | See below |
| `petals` | `dims[]` | `center`, `how`; dim: `icon,name,question,expression,color,score` | 4-8 dims. If **every** dim has `score`, a radar polygon is drawn |
| `triad` | `nodes[3]` | `center{title,body}`; node: `icon,name,body,tag,color` | Exactly 3 nodes |
| `wheel` | `segments[]` | `center`, `how`; segment: `icon,name,sub,body,rows{label:value},color` | 3-8 segments; `rows` render as a detail table |
| `trinity` | `circles[3]` | `outer{icon,name,words[],question,body}`, `center`, `how`; circle: `icon,name,aspiration,question,color` | The ring text repeats `outer.name` + `words` |
| `vmv` | `vision`, `mission` | `pillars[{icon,title,body,color}]`, `values[{name,desc}]`, `identity{title,body}`, `labels{vision,mission,pillars,values,identity}` | 3-5 pillars, 5-7 values |
| `ecosystem` | `hub{}`, `nodes[]` | `flows[{from,to,label}]`, `outcomes[]`; node: `id,icon,title,body,color` | 3-8 nodes; `from`/`to` are node ids or `"hub"`. Opposite-direction twins are curved apart. Phones get a list |
| `cycle` | `steps[]` | `center`, `period` (ms per loop); step: `icon,title,body,color` | 4-8 steps; phones get a numbered list |
| `chain` | `nodes[]` | node: `icon,title,body,sub,via,color` | 3-5 nodes; `via` labels the arrow *into* that node |
| `layers` | `layers[]` | `arrow{label,direction:"up"/"down"}`; layer: `icon,title,purpose,body,items[],color` | List top layer first; they build bottom-up |
| `roadmap` | `phases[]` | `now` (index); phase: `icon,when,title,goal,items[],color` | 3-6 phases; vertical on phones |
| `scores` | `criteria[]`, `items[]` | `max` (10), `top` (3); criterion: `icon,name,desc`; item: `name,scores[],note` | Each `scores` length = criteria count. Sorted by total; headers re-rank |
| `compare` | `columns[]` | `question`; column: `icon,title,tag,body,points[],pros,cons,recommended,color` | 2-3 columns; `pros`/`cons` render as attraction / challenge |
| `questions` | `prompts[]` | prompt: `q,hint,color` | 3-6 prompts |
| `image` | `src` | `caption`, `credit`, `alt`, `paras[]`, `bullets[]` | `src` is relative to the spec and embedded as base64. Credit third-party images |
| `closing` | `words[]` | `kicker`, `title`, `lines[]`, `final` | 4-7 words |

### `venn` in detail

```json
{"type": "venn", "ch": "ikigai", "title": "Where my four circles **meet**",
 "circles": {
   "love": {"title": "What I love", "question": "What makes me feel alive unpaid?", "items": ["🧠 AI", "📚 Teaching"], "summary": "…",
            "label_top": "What I", "label": "LOVE"},
   "good": {…}, "need": {…}, "paid": {…}},
 "overlaps": {"passion": {"expression": "…", "pitfall": "…", "correction": "…"}, "mission": {…}, "profession": {…}, "vocation": {…}},
 "lenses": {"t_no_need": "how this trap shows up for me", "t_no_paid": "…", "t_no_love": "…", "t_no_good": "…"},
 "center": {"label": "Ikigai", "title": "…", "statement": "…", "sub": "risk + correction"}}
```

Region keys for `snap.py --sel` and `?sel=`: `love good need paid passion mission profession vocation t_no_need
t_no_paid t_no_love t_no_good center`. Other interactive types use indices `0,1,2…` (`outer` for the trinity ring).

## Runtime

- Keys: → / Space / Enter next (reveals the slide's remaining fragments first, then scrolls, then advances), ← back,
  Home/End, **M** contents, **T** theme, Esc closes the menu. Swipe on touch screens.
- URL: `#12` opens slide 12 · `?theme=dark|light` · `?static` (snapshot mode: no animation, all fragments shown,
  roadmaps lit, bars full) · `?static&sel=center` preselects an interactive region.
- Print (⎙ or Ctrl/Cmd+P) shows every slide with fragments revealed, one per page.
- Interactive widgets (Venn, petals, wheel, trinity, triad) run a guided tour; clicking any region pauses it, and
  ▶ Play resumes. Respects `prefers-reduced-motion`.
