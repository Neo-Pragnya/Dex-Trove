# Capability acceptance suite

Behaviour-level checks for everything Dex Trove promises, run against the real `dex` CLI (and its website) before
every release. `tests/` proves the parts; this suite proves the product: install the wheel, browse and install
items, learn from upstreams the way a maintainer does, hand the trove to Ananke, and walk the website like a
visitor.

It shares its harness (`harness.py`, the step vocabulary and the release gate) with Ananke Plexus's
`acceptance/`. Ananke's copy is the source of truth, and both copies must stay byte-identical. Read
[Ananke's acceptance README](https://github.com/Neo-Pragnya/Ananke-Plexus/blob/main/acceptance/README.md) for the
full step reference and gate semantics.

## Run it

```bash
make acceptance          # dev environment (~1 min)
make acceptance-wheel    # build the wheel, install it with [ananke] in a fresh venv, run from there (what ships)
make docs-build && make acceptance-site   # browser journeys on the built website (real headless Chrome)
node acceptance/site/journeys.mjs website/dist   # the journeys on their own
```

Reports: `acceptance/report/acceptance.json` and `summary.md`. In CI:

- `acceptance.yml` runs the wheel suite on every push and PR.
- `docs.yml` runs the browser journeys after building the site, and a failure blocks the Pages deploy.
- `release-pypi.yml` runs the gate on the exact wheel it will publish, and publishing waits for it.

## What it covers

| Capability | Blocker | How it is proven |
| --- | --- | --- |
| packaging | yes | version, the whole trove in the wheel, `dex validate`, the `ananke.troves` entry point, fast start |
| catalog | yes | search finds by purpose; kind and source filters; `show` licence/provenance/Ananke ref; `sources` |
| install | yes | Claude Code (project), Copilot, plain folder, plugin → members, the exact command the website shows |
| install-safety | yes | project installs write nothing in `$HOME`; hooks need `--allow-exec` (and the reviewed twin installs) |
| licence | yes | `dex license` on MIT, proprietary ("restrictive terms") and GPL texts |
| learn | yes | a maintainer checkout with two fixture upstreams; the outcomes are listed below |
| privacy | yes | `.dexignore` and the user-level ignore file leave no trace in the trove, EXCLUDED.json, lock or notices |
| notices | | notices credit copyright lines; catalog rebuilds |
| ananke | yes | `dex ananke sync`; `ananke registry learn python:dex-trove` (placeholder secrets refused by design) |
| docs-export | | one page per item for the website |
| site | | journeys: home, catalog search/filters, item page, Mermaid render + hover, highlighting, theme, 404, 390 px |
| cli-ux | | clean errors |

The learn scenarios check each kind of item:

- **admitted:** MIT and Apache items, Apache with its canonical `LICENSE.upstream`, and the `executes-code` tag on
  items with scripts;
- **refused, with the reason recorded:** a proprietary licence, a missing licence, a bundled GPL file, a
  real-format AWS key and an oversized file;
- **dry run:** writes nothing;
- **content change:** bumps the item's version;
- **no credentials:** none ever reach the trove.

Secret-shaped strings and the 6 MB file are **generated at runtime** (see `conftest.py`). Nothing that looks like a
credential is committed.

## Found by this suite (all fixed in 0.1.2)

| What the scenario expected | What was wrong |
| --- | --- |
| An exact duplicate is refused on the first learn | duplicates were only detected against items from *previous* runs |
| Learning twice from unchanged upstreams changes nothing | the second learn removed the duplicate the first admitted |
| Refusing to install exits non-zero | `dex install <hook>` without `--allow-exec` installed nothing and exited 0 |
| `dex validate` in a checkout checks that checkout (wheel run) | an installed `dex` validated the wheel's trove against the checkout's notices |

When a new problem is found, add a `@known_issue` scenario that states the correct behaviour, and list it here. The
harness, scaffolder and probe ship as the **`neo-pragnya/capability-acceptance`** skill.
