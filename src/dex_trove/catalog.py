"""Read-side catalog: list, search, resolve references (works offline from the installed wheel)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dex_trove.paths import KIND_DIRS, trove_root


class RefError(LookupError):
    pass


def load(trove: Path | None = None) -> list[dict[str, Any]]:
    path = (trove or trove_root()) / "catalog.json"
    if not path.is_file():
        return []
    items: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8")).get("items", [])
    return items


def filter_items(
    items: list[dict[str, Any]], *, kind: str | None = None, source: str | None = None
) -> list[dict[str, Any]]:
    return [i for i in items if (not kind or i["kind"] == kind) and (not source or i["namespace"] == source)]


def search(items: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Weighted lexical search: name > title > tags > description."""
    words = [w for w in query.lower().split() if w]
    scored = []
    for it in items:
        fields = (
            (it["name"], 5),
            (it.get("title", "").lower(), 3),
            (" ".join(it.get("tags", [])), 2),
            (it.get("description", "").lower(), 1),
        )
        score = 0
        for w in words:
            hit = sum(weight for text, weight in fields if w in text)
            if not hit:
                score = 0
                break
            score += hit
        if score:
            scored.append((score, it))
    scored.sort(key=lambda p: (-p[0], p[1]["id"]))
    return [it for _, it in scored]


def resolve(items: list[dict[str, Any]], ref: str) -> dict[str, Any]:
    """``kind:ns/name``, ``ns/name`` or a unique bare ``name``."""
    kind = None
    if ":" in ref:
        kind, ref = ref.split(":", 1)
        if kind not in KIND_DIRS:
            raise RefError(f"unknown kind {kind!r}")
    pool = filter_items(items, kind=kind)
    hits = [i for i in pool if i["id"] == ref] if "/" in ref else [i for i in pool if i["name"] == ref]
    if not hits:
        raise RefError(f"no item matches {ref!r}")
    if len(hits) > 1:
        options = ", ".join(f"{h['kind']}:{h['id']}" for h in hits)
        raise RefError(f"{ref!r} is ambiguous: {options}")
    return hits[0]


def item_path(item: dict[str, Any], trove: Path | None = None) -> Path:
    return (trove or trove_root()) / str(item["dir"])
