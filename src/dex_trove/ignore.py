"""Ignore rules that live *outside* the Dex-Trove repo (DESIGN.md §6, "Private items").

Two places are read, so personal items never need to be named in this repository:

1. ``<source root>/.dexignore`` — e.g. ``~/Documents/Repositories/Skills/.dexignore`` next to the skills it hides.
2. A user-level file: ``$DEX_TROVE_IGNORE`` or ``~/.config/dex-trove/ignore``. Lines may be scoped to one source
   with ``<source-id>:<pattern>``; unscoped lines apply to every source.

Patterns are ``fnmatch`` globs matched against the item's name, its slugified name and its path relative to the
source root (and that path's first and last segments). ``#`` starts a comment. Ignored items are skipped *silently*: they are
not copied, not listed in ``EXCLUDED.json`` and not recorded in the lock, so no trace of them reaches the repo.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

DEXIGNORE = ".dexignore"


def user_ignore_file() -> Path:
    env = os.environ.get("DEX_TROVE_IGNORE")
    if env:
        return Path(env).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
    return Path(base).expanduser() / "dex-trove" / "ignore"


def _lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


def load_patterns(source_id: str, root: Path) -> list[str]:
    patterns = _lines(root / DEXIGNORE)
    for line in _lines(user_ignore_file()):
        scope, sep, pattern = line.partition(":")
        if not sep:
            patterns.append(line)
        elif scope.strip() in {source_id, "*"}:
            patterns.append(pattern.strip())
    return patterns


def is_ignored(names: list[str], rel_path: str, patterns: list[str]) -> bool:
    if not patterns:
        return False
    rel = rel_path.strip("/")
    candidates = {n for n in names if n} | {rel, rel.split("/", 1)[0], rel.rsplit("/", 1)[-1]}
    return any(fnmatch.fnmatch(c, p) for c in candidates for p in patterns)
