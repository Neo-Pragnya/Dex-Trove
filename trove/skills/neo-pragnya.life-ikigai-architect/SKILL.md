---
name: life-ikigai-architect
description: "Life Ikigai Architect: turn a person's reflections, journals, notes or purpose conversations into a personal Ikigai, vision, mission, values and roadmap, delivered as one self-explanatory, animated HTML presentation (interactive four-circle Ikigai Venn, six-dimension petals, archetype triad, vision-to-values cascade, five-function wheel, ecosystem with live flows, scoring heatmap, roadmaps with a moving comet, reflection prompts). Use whenever someone wants to find or articulate their Ikigai, life purpose, personal mission or vision statement, calling or vocation, dharma, life design or life architecture, a personal strategy or 90-day plan that ties meaning to money, or to choose between career paths or ventures by purpose. Also when they share a purpose or career conversation, a journal, or an Ikigai note and ask to make it visual, a deck, a vision board or presentation, or a skill for others to do the same, even if they don't say Ikigai."
---

# Life Ikigai Architect

Turn the raw material of a life (notes, journals, a long conversation about purpose, or answers to a guided interview)
into a **life architecture**: what the person loves, is good at, the world needs and will pay for; where those meet;
who they are becoming; their vision, mission and values; the operating principles they choose to live by; the ecosystem
they want to build; how they will sequence it; and the inner compass that keeps it honest. The output is **one
self-contained, animated HTML presentation** that explains itself to anyone who opens it.

It works like architecture-as-code: content lives in a JSON **spec**, `scripts/build_deck.py` renders it. A spec is
easy to revise as the person changes, diffable, and re-renders every animation consistently.

## What you produce

| Output | How | Notes |
|---|---|---|
| The deck | `build_deck.py spec.json --out <name>.html` | One file, no external scripts, works offline (Google Fonts optional). Keyboard, swipe, contents menu (M), light/dark (T), print to PDF (⎙) |
| The spec | `spec.json` beside the deck | The person's editable source of truth. Keep it out of this skill folder: it is personal |
| QA screenshots | `scripts/snap.py deck.html --all` | Headless Chrome; `?static` snapshot mode; phone sizes via an iframe |

Signature visuals (all data-driven): the classic four-circle Ikigai recreated as an **interactive SVG in its familiar
palette** (yellow love, lime skill, salmon need, mint pay, deep-green centre), with the four "near-Ikigai" warnings on
dotted leader lines, and a guided tour; a **vision → mission → pillars → values → identity** cascade with a falling
light beam; a **Pañcakṛtya-style wheel**; an **ecosystem** whose flows carry a moving packet and a live caption;
**roadmaps** where a comet travels the track and lights each phase; a **scoring heatmap** you can re-rank by any lens.

## Workflow

1. **Gather the material before designing anything.** If the person has documents (purpose conversations, Ikigai
   notes, journals, CVs), read them fully; they are the primary source and their words beat yours. If material is thin,
   run the interview in `references/reflection-protocol.md` in short rounds (3-5 questions at a time, never a
   40-question wall). Extract into the sections listed there; note contradictions and open questions, don't resolve
   them silently.
2. **Synthesise with the frameworks** in `references/frameworks.md`: four circles → overlaps and pitfalls → six
   dimensions → the connecting principle → archetype → vision, mission, values → operating principles → ecosystem →
   scoring and sequencing → roadmaps → inner compass. Use only the frameworks that fit this person. Pañcakṛtya and
   Iccha-Jñāna-Kriyā are one person's devotional lens; for someone else, use their own tradition (Stoic virtues,
   Christian vocation, the Buddhist pāramitās, a family motto) or leave it out.
3. **Draft the statements with the person, not for them.** Vision, mission, Ikigai sentence and values are offered as
   drafts ("tentative formulation") built from their phrases. If you can, show 2-3 options and let them choose.
4. **Write the spec.** Start from `assets/examples/starter.json` (minimal, with TODOs) or
   `assets/examples/maya_example.json` (a full 24-slide arc using every slide type). Fields: `references/spec-reference.md`
   or `python scripts/build_deck.py --list-types`. Follow the deck blueprint below.
5. **Build:** `python scripts/build_deck.py life.json --out Life_Ikigai.html`. The build validates first (unknown types,
   missing fields, undeclared chapters, triad ≠ 3 nodes, score rows of the wrong length, bad ecosystem ids).
6. **Look at it, then fix it.** `python scripts/snap.py Life_Ikigai.html --all --out shots/` (add `--theme dark`,
   `--size 390x844`, `--sel center` for the Venn centre, and `--offline` when there is no network). Check: text clipped
   in cards, a slide whose main visual falls below the fold at 1440×900, Venn labels, the phone layout. Iterate.
   Never verify animations with headless "virtual time": it doesn't advance CSS animations, so use `?static`.
7. **Hand over:** the deck path, the spec path, how to edit and rebuild, and what you inferred versus quoted. Offer to
   publish only if they want to share it: the content is personal.

## Deck blueprint (the arc that makes it self-explanatory)

| Chapter | Slides (type) |
|---|---|
| Opening | `hero` (name, one-line Ikigai, 生き甲斐) · `statement` (the question beneath the question) · `agenda` |
| What contribution means (optional) | `cards` (impact ≠ reach) · `compare` (world vs self evolution) · `triad` (will/knowledge/action) · `chain` (relief → empowerment) |
| Ikigai map | `image` (the classic model, if the person supplies one, credited) · **`venn`** · four `cards` deep-dives · `petals` (six dimensions) · `table` (interests → one principle) |
| Identity, vision & mission | `triad` (archetype) · **`vmv`** · `statement` (purpose, inward, generational) · `trinity` (+ sustainability ring) |
| Operating principles | `wheel` (their 3-8 principles) · `chain` (how beneficiaries become creators) |
| Ecosystem | `cycle` (the roles feeding each other) · **`ecosystem`** · `cards` (parts in detail, with a boundaries card) · `layers` (who pays vs who benefits) |
| Strategy | `chain` (sequencing) · **`scores`** · `cards` (north star) · `compare` (life architectures, one `recommended`) |
| Roadmap | **`roadmap`** ×2-4 (stages, first 90 days, contribution path, generations) · `layers` (three layers of a life) |
| Inner compass | `cards` tone `warn` (pitfalls → remedies) · `table` (symbolic timing, if they use it) · `questions` (review practice) · `compare` (Life A / Life B) |
| Close | `cycle` (purpose as process) · `questions` (contemplations) · `statement` (an image) · `closing` |

Around 25-50 slides. Every slide gets a `kicker` (where we are), a `title` with one **bold** phrase (rendered as a
gradient), an `intro` that tells a newcomer how to read it, and often a `summary` (the takeaway). That is what makes
the deck understandable without a presenter.

## Principles

- **Their voice, first person.** Write as the person ("I build…"). Quote their phrases; mark synthesis as a draft. Use
  the pronouns they use; otherwise write in first person or use they/them.
- **Honest numbers only.** Never invent scores, revenues or timelines. If they haven't scored their ideas, ask them to,
  or use `petals` without scores rather than a fake radar.
- **Boundaries are part of the design.** Astrology, energy work and other symbolic systems are presented as
  reflective, symbolic lenses, not prediction. Anything about health stays educational and says it doesn't replace
  clinicians. Don't present diagnostic claims (iris, palm, face readings) as validated. This is reflection, not
  therapy: if distress shows up, be human and point to real support.
- **Integrate, don't flatter.** Include the pitfalls, the trade-offs and the questions they haven't answered. A
  purpose deck without its shadow side is a brochure.
- **Sustainability is a design constraint.** Health, relationships and joy belong in the architecture, not as an
  afterthought.
- **Privacy.** Personal specs, images and decks stay in the person's own folder, never inside this skill. Images they
  supply (a reference diagram, a photo) are embedded only into their deck, with a credit line if it's third-party.

## Bundled resources

| Path | What |
|---|---|
| `scripts/ikigai_deck.py` | Engine: 22 slide types, CSS/JS runtime, validation (`build_html`, `load_spec`, `validate`) |
| `scripts/build_deck.py` | CLI: spec → validated, self-contained HTML; `--check`, `--list-types` |
| `scripts/snap.py` | Headless-Chrome screenshots (`?static` mode, `--theme`, `--sel`, phone sizes, `--offline`) |
| `references/reflection-protocol.md` | Interview rounds and what to extract from documents |
| `references/frameworks.md` | The frameworks, how to fill each one, and which slide renders it |
| `references/spec-reference.md` | Every slide type and field, limits, runtime URL parameters |
| `assets/examples/maya_example.json` | Full fictional example (all slide types) |
| `assets/examples/starter.json` | Minimal starter with TODOs |
| `assets/previews/` | Screenshots of the example deck |

Requirements: Python 3.9+ (standard library only). Chrome or Chromium only for `snap.py`.
