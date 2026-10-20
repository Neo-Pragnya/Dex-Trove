# Contributing to Dex Trove

Thanks for helping grow a library that people can reuse without licence surprises. We welcome new sources,
adapters, first-party skills, fixes, tests and documentation.

Please read the [Code of Conduct](CODE_OF_CONDUCT.md) first.

## Ways to contribute

| You want to… | Start here |
| --- | --- |
| Propose a new upstream repo | [Adding a source](docs/guides/adding-a-source.md): check the licence, then add it under `candidates:` in `sources.yaml` |
| Add a first-party skill | [First-party skills](docs/guides/first-party-skills.md) |
| Fix a misclassified licence | Open an issue with the item id, the licence file and the correct SPDX id |
| Improve the CLI, adapters or guards | The steps below |
| Improve the docs or website | [Docs site](docs/guides/docs-site.md) |

## 1. Fork, clone, branch

```bash
git clone https://github.com/Neo-Pragnya/Dex-Trove.git
cd Dex-Trove
git checkout -b feature/my-change
```

## 2. Set up

Dex Trove uses [uv](https://docs.astral.sh/uv/) for everything, like Ananke Plexus:

```bash
make install          # uv sync --all-extras  (includes ananke-plexus for strict manifest validation)
pre-commit install    # optional: ruff + dex validate on commit
```

## 3. Make the change

- Keep pull requests focused. A trove refresh (`dex learn`) and a code change belong in separate PRs.
- **Never edit files under `trove/` by hand.** They are verbatim upstream bytes plus generated files, and
  `dex validate` fails on any drift. Change `sources.yaml` or the code, then re-learn.
- Update the docs in `docs/` when behaviour, configuration or output changes.
- Add tests in `tests/`. The fixtures in `tests/conftest.py` build a miniature upstream repo that covers each
  admission rule.

## 4. Validate locally

```bash
make verify           # ruff check + ruff format --check + mypy (strict) + pytest + dex validate
make docs-build       # dex docs export + astro check + astro build
```

## 5. Open a pull request

Include:

- a summary of the change and why it is needed
- for trove changes: the `dex learn` summary line(s), and any new entries in `trove/EXCLUDED.json`
- validation results (and screenshots for website changes)

Reviewers check every new source and every newly admitted licence. When in doubt, a licence stays out.

## Reporting issues

Use the [issue tracker](https://github.com/Neo-Pragnya/Dex-Trove/issues). For security problems, follow
[SECURITY.md](SECURITY.md) instead.

## Licensing of contributions

Code and docs you contribute are licensed under the repository's MIT licence. First-party skills you add under
the `neo-pragnya` source are also MIT. Content learned from upstream keeps its upstream licence.
