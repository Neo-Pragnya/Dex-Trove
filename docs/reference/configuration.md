---
title: Configuration & environment
description: Environment variables, file locations, Make targets and package extras.
---

# Configuration & environment

## Environment variables

| Variable | Default | Effect |
| --- | --- | --- |
| `DEX_TROVE_ROOT` | — | Use this directory as the trove (must contain `catalog.json` and the kind folders). Overrides the installed package and the checkout. |
| `DEX_TROVE_CACHE` | `$XDG_CACHE_HOME` or `~/.cache`, + `/dex-trove` | Where upstream sources are cloned (`<cache>/sources/<id>`) |
| `XDG_CACHE_HOME` | `~/.cache` | Fallback base for the cache |
| `DEX_TROVE_IGNORE` | `$XDG_CONFIG_HOME/dex-trove/ignore` (`~/.config/…`) | User-level ignore rules (`[source:]pattern` per line), merged with each source's own `.dexignore` |
| `UV_PUBLISH_TOKEN`, `UV_PUBLISH_TOKEN_TESTPYPI` | — | Manual publish tokens (`make publish-*`), read from `.env` |
| `SITE_BASE` | `/` | Base path for the Astro build (`/Dex-Trove/` on GitHub Pages) |

## How the trove is located

`dex_trove.paths.trove_root()`:

1. `$DEX_TROVE_ROOT`, if set;
2. the installed package directory, if it contains `catalog.json` (normal `pip install`);
3. `<checkout>/trove`, when run inside a Dex-Trove checkout (found by walking up to `sources.yaml` +
   `src/dex_trove/`);
4. the package directory (empty catalog).

Write commands (`learn`, `notices`, `catalog`, `docs export`) always operate on a checkout.

## Package extras

| Extra | Installs | Use |
| --- | --- | --- |
| *(none)* | PyYAML, typer, rich | the CLI and the library |
| `ananke` | `ananke-plexus` | strict manifest validation in `dex validate`; the `ananke` CLI for `dex ananke sync` |
| `dev` | pytest, pytest-cov, ruff, mypy, types-PyYAML, hatchling | development |

## Make targets

| Target | Does |
| --- | --- |
| `install` | `uv sync --all-extras` |
| `lint` / `format` / `format-check` | ruff |
| `typecheck` | mypy (strict) |
| `test` / `coverage` | pytest (HTML coverage in `htmlcov/`) |
| `validate` | `dex validate` |
| `verify` | lint + format-check + typecheck + test + validate |
| `learn` / `notices` | `dex learn` / `dex notices` |
| `trivy-scan` / `trivy-scan-json` / `trivy-scan-sarif` | Trivy on package code + deps (skips `trove/`) |
| `security` | Trivy + pip-audit |
| `build` / `build-check` / `sbom` | `uv build`, `twine check`, CycloneDX SBOM |
| `docs-export` / `docs-install` / `docs-build` / `docs-serve` | the Astro site |
| `publish-testpypi` / `publish-pypi` | manual publish (runs `verify` + `build-check` first) |
| `clean` | remove build and cache outputs |

## Files

| Path | Purpose |
| --- | --- |
| `sources.yaml` | source map ([reference](sources-yaml.md)) |
| `trove/` | the library ([item format](item-format.md), [trove files](trove-files.md)) |
| `THIRD_PARTY_NOTICES.md` | aggregated attribution |
| `.env` / `.env.example` | local publish tokens (gitignored) / template |
| `.trivyignore`, `.gitleaks.toml` | scanner configuration |
| `.pre-commit-config.yaml` | ruff + `dex validate` hooks (never rewrites `trove/`) |
| `uv.lock` | locked dependencies |
| `website/` | docs site |
| `~/.cache/dex-trove/sources/<id>` | upstream clones |
| `<source root>/.dexignore` | per-source ignore rules, kept next to the content (outside this repo) |
| `~/.config/dex-trove/ignore` | user-level ignore rules |

## Entry points

| Group | Name | Target |
| --- | --- | --- |
| `console_scripts` | `dex` | `dex_trove.cli:app` |
| `ananke.troves` | `dex-trove` | `dex_trove.paths:trove_root` |
