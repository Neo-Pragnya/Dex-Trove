---
title: Python API
description: Using dex_trove from Python — catalog lookup, installation, licence classification and learning.
---

# Python API

The CLI is the stable interface. The modules below are importable and used by the CLI, but their signatures
may change before 1.0.

## Catalog: `dex_trove.catalog`

```python
from dex_trove import catalog

items = catalog.load()                                   # list[dict] — every dex.json record
skills = catalog.filter_items(items, kind="skill", source="superpowers")
hits = catalog.search(items, "terraform review")         # ranked
item = catalog.resolve(items, "awesome-copilot/git-commit")   # or "git-commit", "skill:awesome-copilot/git-commit"
path = catalog.item_path(item)                           # Path to the item directory
```

`resolve` raises `catalog.RefError` for unknown or ambiguous references.

## Installing: `dex_trove.install`

```python
from pathlib import Path
from dex_trove.install import install

done = install(["superpowers/systematic-debugging", "awesome-copilot/arize-ax"],
               target="copilot", path=Path("./.github"))
for d in done:
    print(d.id, d.kind, d.dest, d.skipped)
```

`Installed(id, kind, dest: Path | None, skipped: str)`. `dest` is `None` when skipped. Raises `InstallError`.

## Licences: `dex_trove.licenses`

```python
from pathlib import Path
from dex_trove import licenses

licenses.classify_text(open("LICENSE").read())   # ('MIT', 'MIT text')
licenses.classify_file(Path("LICENSE"))          # Classification(spdx, verdict, evidence, notice)
licenses.evaluate_expression("MIT OR GPL-3.0-only")   # ('MIT', 'allow')
licenses.verdict_for("MPL-2.0")                  # 'review'
licenses.classify_frontmatter("Complete terms in LICENSE.txt")  # None → look at files
```

## Ananke: `dex_trove.ananke_bridge`

```python
from pathlib import Path
from dex_trove import ananke_bridge

selected, proc = ananke_bridge.sync(project=Path("."), kinds=["skill"], sources=["neo-pragnya"])
print(len(selected), proc.returncode, proc.stdout)
```

## Learning: `dex_trove.learn` (checkout only)

```python
from pathlib import Path
from dex_trove import learn, sources

srcs, _ = sources.load(Path("sources.yaml"))
src = next(s for s in srcs if s.id == "awesome-copilot")
root, commit = sources.fetch(src, prefer_local=True)
learner = learn.Learner(Path("trove"), dry_run=True)
result = learner.learn(src, root, commit, {s.id: s.priority for s in srcs})
print(len(result.items), [e.reason for e in result.excluded])
# learn.finalize(Path("trove"), [result], srcs)  # when not a dry run
```

## Locating the trove: `dex_trove.paths`

```python
from dex_trove.paths import trove_root, KIND_DIRS
trove_root()        # Path — see Configuration › How the trove is located
KIND_DIRS["skill"]  # 'skills'
```
