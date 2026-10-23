---
title: Adding a source
description: Evaluate a repository, map it in sources.yaml, learn it, and (if needed) write an adapter.
---

# Adding a source

## 1. Evaluate the licence first

Check the repo-level licence, and whether items carry their own:

```bash
gh api repos/OWNER/REPO --jq '.license.spdx_id'
gh api "repos/OWNER/REPO/git/trees/HEAD?recursive=1" \
  --jq '.tree[].path | select(test("(^|/)(LICEN[CS]E|COPYING)[^/]*$"; "i"))'
```

| Finding | Decision |
| --- | --- |
| Permissive repo licence (MIT, Apache-2.0, …) | Good candidate. Items are still checked one by one. |
| No repo licence, but per-item licence files | Possible. Only items with their own allowed licence will be admitted. |
| No licence anywhere | **Not importable.** Record it as a candidate with that decision. |
| Copyleft, NC/ND, share-alike | Deny or review. Discuss in an issue before mapping. |
| A link list ("awesome-…" with no content) | Use it to discover other repos; don't learn from it. |

Add the result to `candidates:` in `sources.yaml` even if you don't enable it. The
[Sources](https://neo-pragnya.github.io/Dex-Trove/sources/) page shows it, so the evaluation isn't repeated.

```yaml
candidates:
  - { repo: OWNER/REPO, license: MIT, decision: "Mapped — enable after review", offers: "What it contains" }
```

## 2. Map it

```yaml
sources:
  - id: huggingface                 # becomes the namespace: huggingface/<item>
    title: Hugging Face Skills
    description: ML and Hugging Face Hub skills.
    adapter: agent-skills           # agent-skills | awesome-copilot | md-agents
    repo: https://github.com/huggingface/skills
    ref: main
    options: { roots: [skills] }    # adapter options
    license: { expected: Apache-2.0 }
```

**Order matters.** Earlier sources win duplicates. Put original authors before aggregators that copy them, so
(for example) `anthropic` comes before `composio`.

The full schema is in the [`sources.yaml` reference](../reference/sources-yaml.md).

## 3. Learn and review

```bash
dex learn huggingface --dry-run      # counts and exclusion reasons, writes nothing
dex learn huggingface
dex validate
git diff --stat trove/ && git diff trove/EXCLUDED.json
```

Review:

- **Every exclusion.** Is `license-denied` correct? A `no licence found` often means the item really has none.
- **A sample of admitted items.** Open `dex.json` and check the `license.evidence` matches what you'd expect.
- **`executes-code` items.** Skim the scripts.
- **`secret` and `secret-shaped` exclusions.** `secret` matched a real key format. `secret-shaped` is usually a
  placeholder in teaching content: it's excluded anyway so the wheel passes package scanners. If an upstream
  item contains a live credential, report it upstream.

Open a PR with the `dex learn` summary line in the description.

## 4. Tune with options

```yaml
    exclude:                         # globs relative to the source root; matching files are withheld
      - "skills/big-demo/assets/*.mp4"
    items:                           # per-item overrides, keyed by item name
      some-skill:
        title: Better Title
        inspired_by:
          - { title: Original idea, url: "https://…" }
    license:
      allow_review: true             # admit 'review' licences (MPL, LGPL, CC-BY-SA) — needs a recorded decision
```

## 5. Writing a new adapter

If the layout isn't covered, add a function to `src/dex_trove/adapters.py`:

```python
def my_layout(root: Path, options: dict[str, Any]) -> Iterator[RawItem]:
    for path in sorted((root / "rules").glob("*.mdc")):
        yield _md_item("instruction", path, name=path.stem, is_dir=False, entry=path.name)


ADAPTERS["my-layout"] = my_layout
```

Rules for adapters:

- **Only find; never decide.** Licence, guards and naming happen in `learn.py`.
- `RawItem.path` is the item directory (`is_dir=True`) or the single file (`is_dir=False`). `entry` is the file
  that describes the item.
- Fill `description`; it drives search, Ananke's `summary` and how agents discover skills.
- Plugins set `members=[(kind, raw_name), …]` and are yielded last, or at least are resolved after the other
  items of the source.
- Add a test fixture in `tests/conftest.py` and assertions in `tests/test_learn.py`.

## 6. Enable in CI

Sources with a `repo:` are re-learned by the weekly `learn` workflow, which opens a PR. Sources with only
`local:` (first-party folders outside git) are skipped in CI; re-learn them locally.
