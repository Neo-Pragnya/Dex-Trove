---
title: Provenance & versioning
description: Pinned commits, content hashes, item SemVer and package versions.
---

# Provenance & versioning

Every item in the trove can answer three questions: **where did this come from**, **has it changed**, and
**which version is it**.

## Where it came from

Each item's `dex.json` records its source:

```json
"source": {
  "id": "awesome-copilot",
  "title": "Awesome GitHub Copilot",
  "repo": "https://github.com/github/awesome-copilot",
  "commit": "613efc8c21d9b3ce642dff361d17006cd9967e28",
  "path": "skills/git-commit",
  "url": "https://github.com/github/awesome-copilot/tree/613efc8c…/skills/git-commit",
  "author": null
}
```

- `commit` is the exact upstream commit the item was copied from, so the `url` is a permanent link.
- First-party items (from a local, non-git folder) have `commit: null`, and their `url` points into this
  repository's copy under `trove/`.
- `trove/trove.lock.json` records the commit for every source, so a `dex-trove` release is reproducible: the same
  version always contains the same items from the same commits.

Ananke receives the same information: the manifest's `metadata.homepage` is the pinned upstream URL,
`metadata.repository` is the repo, and `ananke_id` (`urn:dex-trove:<kind>:<ns>:<name>`) gives the item a stable
identity across versions.

## Has it changed?

Dex computes:

- `files`: every upstream file path in the item (generated files excluded).
- `entry_hash`: SHA-256 of the entry file, used for cross-source duplicate detection.
- `content_hash`: SHA-256 over the sorted `{path: sha256(bytes)}` map of all upstream files.

`dex validate` recomputes the content hash for every item and fails on any mismatch, so hand edits under `trove/`
are caught in CI. Because upstream bytes are never modified, a re-learn diff shows exactly what changed upstream.

## Item versions

Each item has its own SemVer in `dex.json` and `ananke.yaml`:

| Situation | Version |
| --- | --- |
| First time learned | `1.0.0` |
| Re-learned, content hash unchanged | unchanged (and `learned_at` unchanged, so diffs stay quiet) |
| Re-learned, content changed | patch bump: `1.0.0` → `1.0.1` |
| Upstream declares a version (e.g. `plugin.json` `"version": "2.1.0"`, or `version:` frontmatter) | the upstream version (normalised: `1.2` → `1.2.0`, `v3.0.1` → `3.0.1`) |

So `ananke registry learn` registers a new immutable version **only when content actually changed**. Re-running
it after an unchanged release is a no-op (Ananke reports the items as `skipped`).

## Package versions

`dex-trove` itself follows SemVer, `0.x` while the format settles:

- **Patch**: trove refresh, fixes.
- **Minor**: new sources, new kinds, new CLI features, format additions.
- **Major** (after 1.0): incompatible changes to the item format or CLI.

Every release ships a fixed trove snapshot. `CHANGELOG.md` summarises trove changes per release; the git history
of `trove/` is the detailed record.

## Removal

If an item disappears upstream, or becomes excluded (for example because its licence changed), the next learn
deletes its directory and, if excluded, adds it to `EXCLUDED.json`. Ananke registries that already registered it
keep their immutable copy. Use Ananke's lifecycle commands (`deprecate`, `yank`) if needed.
