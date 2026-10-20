"""Where the trove lives: inside an installed wheel, or at the repo root during development."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent

# Dex kind → directory name (also the Ananke-visible directory inside the wheel).
KIND_DIRS = {
    "skill": "skills",
    "agent": "agents",
    "instruction": "instructions",
    "prompt": "prompts",
    "hook": "hooks",
    "workflow": "workflows",
    "plugin": "plugins",
}
DIR_KINDS = {v: k for k, v in KIND_DIRS.items()}


def repo_root(start: Path | None = None) -> Path | None:
    """The Dex-Trove checkout containing ``sources.yaml``, searching upward from ``start``."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "sources.yaml").is_file() and (candidate / "src" / "dex_trove").is_dir():
            return candidate
    dev = PACKAGE_DIR.parent.parent
    if (dev / "sources.yaml").is_file():
        return dev
    return None


def trove_root() -> Path:
    """Directory holding ``<kind-plural>/<ns.name>/`` items and ``catalog.json``."""
    env = os.environ.get("DEX_TROVE_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    if (PACKAGE_DIR / "catalog.json").is_file():
        return PACKAGE_DIR
    root = repo_root()
    if root is not None:
        return root / "trove"
    return PACKAGE_DIR


def sources_file() -> Path:
    root = repo_root()
    if root is not None:
        return root / "sources.yaml"
    return PACKAGE_DIR / "sources.yaml"


def cache_dir() -> Path:
    base = os.environ.get("DEX_TROVE_CACHE") or os.environ.get("XDG_CACHE_HOME") or "~/.cache"
    return Path(base).expanduser() / "dex-trove"
