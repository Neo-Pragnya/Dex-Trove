---
title: CLI reference
description: Every dex command, option and exit code.
---

# CLI reference

```text
dex [--version] [--install-completion] [--show-completion] COMMAND [ARGS]...
```

| Command | Purpose | Needs a checkout? |
| --- | --- | --- |
| [`sources`](#dex-sources) | mapped sources and evaluated candidates | no |
| [`learn`](#dex-learn) | fetch sources, admit items, rewrite the trove | **yes** |
| [`validate`](#dex-validate) | CI gate: manifests, licences, hashes, catalog, notices | no (notices check only in a checkout) |
| [`list`](#dex-list) | list items | no |
| [`search`](#dex-search) | search items | no |
| [`show`](#dex-show) | one item's provenance, licence and files | no |
| [`install`](#dex-install) | install into Claude Code, Copilot or a directory | no |
| [`license`](#dex-license) | classify a licence file or directory | no |
| [`notices`](#dex-notices) | regenerate `THIRD_PARTY_NOTICES.md` | **yes** |
| [`catalog`](#dex-catalog) | rebuild `catalog.json` from `dex.json` files | **yes** |
| [`ananke sync`](#dex-ananke-sync) | register items into an Ananke registry | no |
| [`docs export`](#dex-docs-export) | write Astro content for the site | **yes** |

"Needs a checkout" means the command must run inside a Dex-Trove repository (a directory with `sources.yaml` and
`src/dex_trove/`). Read-only commands work from the installed wheel.

`REF` arguments accept `namespace/name`, a unique bare `name`, or `kind:namespace/name`.

---

## `dex sources`

```text
dex sources [--json]
```

Prints the sources in `sources.yaml` (id, adapter, repo or local path, enabled, first-party) and the evaluated
`candidates`. `--json` dumps both lists.

## `dex learn`

```text
dex learn [SOURCE_IDS]... [--dry-run] [--prefer-local] [--no-refresh]
```

Fetches each source and runs the [learn pipeline](../concepts/architecture.md#2-the-learn-pipeline). With no
arguments, all `enabled` sources are learned; named sources are learned even if disabled.

| Option | Effect |
| --- | --- |
| `--dry-run` | report counts and exclusion reasons; write nothing |
| `--prefer-local` | use a source's `local:` path when present instead of cloning `repo:` |
| `--no-refresh` | reuse cached clones without `git fetch` |

Per source it prints `<id> @ <commit>: N admitted, M excluded {reason: count}, K removed`. It then rewrites
`trove/catalog.json`, `trove/EXCLUDED.json`, `trove/trove.lock.json` and `THIRD_PARTY_NOTICES.md`. A source that
fails to fetch is reported (`skip <id>: …`) and its existing items are left untouched.

Exit codes: `0` success, `2` unknown source id or not in a checkout.

## `dex validate`

```text
dex validate
```

Checks the trove in use (the checkout's `trove/`, or the installed package):

- `catalog.json` lists exactly the items on disk
- every item name is valid and its licence verdict is `allow`
- every listed file exists, and the recomputed content hash matches `content_hash` (no drift)
- `ananke.yaml` exists and agrees with `dex.json` (kind, version)
- if `ananke-plexus` is importable, every manifest validates against Ananke's strict `ArtifactManifest` model
- in a checkout, `THIRD_PARTY_NOTICES.md` is current

Prints `✓ N items valid`, or one `✗` line per problem and exits `1`.

## `dex list`

```text
dex list [--kind/-k KIND] [--source/-s NAMESPACE] [--json]
```

Lists items as a table (kind, id, licence, description) or JSON (`kind`, `id`, `version`, `title`).

## `dex search`

```text
dex search QUERY... [--kind/-k KIND] [--source/-s NAMESPACE] [--limit/-n 25] [--json]
```

Every word must match the name, title, tags or description. Results are ranked with weights name 5, title 3,
tags 2, description 1.

## `dex show`

```text
dex show REF [--json]
```

Title, kind, id and version, description, source with pinned upstream URL, licence with evidence, inspirations,
plugin members, files and the local path. `--json` prints the full [`dex.json`](item-format.md#dexjson).
Exit `2` if the ref is unknown or ambiguous.

## `dex install`

```text
dex install REF... [--target/-t claude|copilot|dir] [--scope user|project] [--path DIR] [--allow-exec]
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--target` | `claude` | `claude` (Claude Code), `copilot` (`.github/`), `dir` (full item copy) |
| `--scope` | `user` | for `claude`: `user` → `~/.claude`, `project` → `./.claude` |
| `--path` | — | base directory override; **required** for `--target dir` |
| `--allow-exec` | off | allow installing hooks (they run code automatically) |

Prints `✓ kind:id → destination` for each installed item, and `– kind:id: reason` for skipped ones (an
unsupported kind for the target, or a hook without `--allow-exec`). Plugins expand to their members. See
[Installing items](../guides/installing-items.md). Exit `2` on an unknown ref or target.

## `dex license`

```text
dex license PATH
```

Classifies a licence file, or every licence file directly in a directory:
`PATH: SPDX → verdict (evidence)`. Exit `1` if no licence files are found.

## `dex notices`

```text
dex notices
```

Regenerates `THIRD_PARTY_NOTICES.md` from the trove. `dex learn` does this automatically.

## `dex catalog`

```text
dex catalog
```

Rebuilds `catalog.json` from the `dex.json` files on disk and refreshes `EXCLUDED.json` and the lock without
learning. Use it after resolving a merge conflict in `trove/`.

## `dex ananke sync`

```text
dex ananke sync [--project DIR] [--kind/-k KIND]... [--source/-s NS]... [--name/-n NAME]...
                [--dry-run] [--include-flagged] [--ananke-bin PATH]
```

Runs `ananke registry learn` over the selected items. Filters are repeatable and combined with AND across
option types. `--name` accepts `name` or `ns/name`.

| Option | Meaning |
| --- | --- |
| `--project` | Ananke project directory (default `.`); it must have run `ananke registry init` |
| `--dry-run` | passes `--dry-run` to Ananke |
| `--include-flagged` | also offer items with `secret_flags` (Ananke's `[secrets]` policy then decides) |
| `--ananke-bin` | path to the `ananke` executable if it isn't on `PATH` |

Prints Ananke's output, then `✓ N trove items offered to Ananke`. Exit `2` if `ananke` isn't found or nothing
matches; otherwise Ananke's exit code.

## `dex docs export`

```text
dex docs export [--out website/src]
```

Writes `content/items/*.md` and `data/search.json` + `data/trove.json` under `--out`. See
[Docs site](../guides/docs-site.md).

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | success |
| `1` | validation problems / no licence files found |
| `2` | usage error: unknown ref, source or target; not in a checkout; `ananke` not found |
| other | passed through from `ananke` (`dex ananke sync`) |
