---
title: Item format
description: The normalised item directory, dex.json and ananke.yaml, field by field.
---

# Item format

## Directory

```text
trove/<kind-plural>/<namespace>.<name>/
├── <upstream files>        verbatim copies (entry file + everything bundled with it)
├── LICENSE.upstream        governing licence text, when the item didn't ship one (optional)
├── NOTICE.upstream         nearest upstream NOTICE file, when outside the item (optional)
├── ananke.yaml             generated Ananke manifest
└── dex.json                generated provenance + catalog record
```

`<kind-plural>` is one of `skills`, `agents`, `instructions`, `prompts`, `hooks`, `workflows`, `plugins`. Inside
the wheel the same directories sit under `dex_trove/`.

Single-file upstream items (agents, instructions, workflows) become a folder containing that one file, under its
original filename (e.g. `api-architect.agent.md`).

## `dex.json`

A real example (`trove/skills/awesome-copilot.git-commit/dex.json`):

```json
{
  "id": "awesome-copilot/git-commit",
  "kind": "skill",
  "namespace": "awesome-copilot",
  "name": "git-commit",
  "title": "Git Commit with Conventional Commits",
  "description": "Execute git commit with conventional commit message analysis, …",
  "tags": ["awesome-copilot", "skill"],
  "version": "1.0.0",
  "entry": "SKILL.md",
  "dir": "skills/awesome-copilot.git-commit",
  "source": {
    "id": "awesome-copilot",
    "title": "Awesome GitHub Copilot",
    "repo": "https://github.com/github/awesome-copilot",
    "commit": "613efc8c21d9b3ce642dff361d17006cd9967e28",
    "path": "skills/git-commit",
    "url": "https://github.com/github/awesome-copilot/tree/613efc8c…/skills/git-commit",
    "author": null
  },
  "license": {
    "spdx": "MIT",
    "verdict": "allow",
    "evidence": "frontmatter license: 'MIT'",
    "notice": "Copyright GitHub, Inc.",
    "components": []
  },
  "inspired_by": [],
  "executes_code": false,
  "members": [],
  "files": ["SKILL.md"],
  "entry_hash": "554d1a3c…",
  "content_hash": "2ec73abb…",
  "learned_at": "2026-10-20T03:28:53+00:00"
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | `namespace/name` (unique per kind) |
| `kind` | enum | `skill` `agent` `instruction` `prompt` `hook` `workflow` `plugin` |
| `namespace` | string | source id |
| `name` | string | slugified name: `^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$` |
| `title` | string | display title: `sources.yaml` override, else frontmatter `title`/`name` (non-skills), else first H1, else name |
| `description` | string | frontmatter `description`, else the first ~400 characters of the body |
| `tags` | string[] | upstream `tags`/`keywords` + kind + namespace + `executes-code` / `ananke-secret-flag` when applicable |
| `version` | SemVer | item version ([rules](../concepts/provenance-and-versioning.md#item-versions)) |
| `entry` | string | entry file, relative to the item directory |
| `dir` | string | item directory, relative to the trove root |
| `source.id` / `title` / `repo` | | the source |
| `source.commit` | string \| null | upstream commit learned (null for non-git local folders) |
| `source.path` | string | item path inside the source |
| `source.url` | string \| null | pinned link to the item upstream (or into this repo for first-party items) |
| `source.author` | string \| null | upstream `author` (frontmatter or `plugin.json`) |
| `license.spdx` | string | SPDX id of the governing licence |
| `license.verdict` | `allow` | always `allow` for admitted items |
| `license.evidence` | string | where the verdict came from (file and fingerprint, or frontmatter value) |
| `license.notice` | string | copyright line(s) extracted from the governing text |
| `license.components` | string[] | other allowed licences found in nested files (e.g. `OFL-1.1` fonts) |
| `inspired_by` | `{title, url}[]` | from `sources.yaml` `items` |
| `executes_code` | bool | contains scripts or `hooks.json` |
| `members` | string[] | plugins only: `kind:namespace/name` of each admitted member |
| `files` | string[] | upstream files in the item (sorted; generated files excluded) |
| `entry_hash` | sha256 | of the entry file (duplicate detection) |
| `content_hash` | sha256 | over `{path: sha256}` of all `files` (drift detection, versioning) |
| `learned_at` | ISO-8601 | when the current content was first learned (unchanged if content is unchanged) |
| `apply_to` | string | instructions only: upstream `applyTo` glob |
| `secret_flags` | string[] | `rule path:line` for each line Ananke's scanner would refuse (no values) |
| `notes` | string[] | e.g. skipped symlinks, files withheld by `exclude` globs |

## `ananke.yaml`

Generated to satisfy Ananke's strict `ArtifactManifest` schema (unknown fields are rejected):

| Field | Value |
| --- | --- |
| `kind` | `skill`, `agent`, `prompt` (instruction/prompt), `tool` (hook), `workflow`, `bundle` (plugin) |
| `namespace`, `name`, `version` | from `dex.json` |
| `ananke_id` | `urn:dex-trove:<dex-kind>:<namespace>:<name>`, a stable identity across versions |
| `summary` | first sentence(s) of the description, ≤ ~200 chars |
| `description` | full description |
| `runtime.supported` | `[claude-code, github-copilot, generic]` |
| `instructions.ref` | agents and prompts: the entry file |
| `permissions` | items **without** code: explicitly empty (`filesystem` read/write `[]`, `shell.allow: []`, `network: []`). Items with code: omitted, so Ananke warns until reviewed. |
| `members` | plugins: `[{ref: ananke://<kind>/<ns>/<name>, version: '*'}]` |
| `license` | `{expression: <spdx>, source: <evidence>, approval: approved}` |
| `metadata` | `{tags, homepage: <pinned upstream url>, repository: <repo>}` |

## Ananke-side identity

| | Example |
| --- | --- |
| URI | `ananke://skill/awesome-copilot/git-commit@1.0.0` |
| Reference | `awesome-copilot/git-commit@^1` |
| Installed layout | `.ananke/skills/installed/awesome-copilot.git-commit@1.0.0/` |
