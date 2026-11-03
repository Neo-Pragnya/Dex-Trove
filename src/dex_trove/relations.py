"""Typed relations between items (docs/concepts/related-items.md).

Every relation has a type, an origin and evidence:

- ``curated``: reviewed in ``taxonomy/relations.yaml`` (requires, complements, alternative-to);
- ``derived``: facts Dex already holds (part-of, bundles from plugin members; forked-from, replaced-by from the
  release ledger);
- ``inferred``: ``similar``, from shared tags and name words. A hint for browsing only.

No relation type says two items are *compatible*. Whether something runs in your setup depends on its inputs,
requirements and your tools, which a harness such as Ananke checks at resolve time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from dex_trove import releases

RELATIONS_FILE = "relations.json"
CURATED_TYPES = {"requires": "requires", "complements": "complements", "alternative-to": "alternative-to"}
SYMMETRIC = {"complements", "alternative-to"}
INVERSE = {
    "requires": "required-by",
    "part-of": "bundles",
    "forked-from": "forked-as",
    "replaced-by": "replaces",
}
TYPES = (
    "requires", "required-by", "complements", "alternative-to", "part-of", "bundles",
    "forked-from", "forked-as", "replaced-by", "replaces", "similar",
)  # fmt: skip
ORIGIN_RANK = {"curated": 0, "derived": 1, "inferred": 2}


class RelationError(ValueError):
    pass


def curated_file() -> Path:
    return Path(__file__).resolve().parent / "taxonomy" / "relations.yaml"


def load_curated(path: Path | None = None) -> list[dict[str, str]]:
    data = yaml.safe_load((path or curated_file()).read_text(encoding="utf-8")) or {}
    return list(data.get("relations", []) or [])


def _namespace(key: object) -> str:
    return str(key).partition(":")[2].partition("/")[0]


def applicable(curated: list[dict[str, str]], keys: set[str]) -> list[dict[str, str]]:
    """Relations about sources this trove learned. Others describe a trove we don't hold, and are skipped."""
    learned = {_namespace(k) for k in keys}
    return [r for r in curated if _namespace(r.get("from")) in learned and _namespace(r.get("to")) in learned]


def _check_curated(curated: list[dict[str, str]], keys: set[str]) -> None:
    """Within learned sources a missing endpoint is dangling, and an error."""
    problems: list[str] = []
    requires: dict[str, set[str]] = {}
    for i, r in enumerate(curated):
        where = f"relations.yaml entry {i + 1} ({r.get('from')} {r.get('type')} {r.get('to')})"
        if r.get("type") not in CURATED_TYPES:
            problems.append(f"{where}: type must be one of {', '.join(CURATED_TYPES)}")
        if not str(r.get("evidence") or "").strip():
            problems.append(f"{where}: evidence is required")
        for end in ("from", "to"):
            if r.get(end) not in keys:
                problems.append(f"{where}: {end} {r.get(end)!r} is not a trove item")
        if r.get("from") == r.get("to"):
            problems.append(f"{where}: an item can't relate to itself")
        if r.get("type") == "requires":
            requires.setdefault(str(r["from"]), set()).add(str(r["to"]))
    # requires must not loop: a cycle would mean nothing can be loaded first
    state: dict[str, int] = {}

    def visit(n: str, path: list[str]) -> None:
        state[n] = 1
        for m in requires.get(n, ()):
            if state.get(m) == 1:
                problems.append("requires cycle: " + " → ".join([*path, n, m]))
            elif not state.get(m):
                visit(m, [*path, n])
        state[n] = 2

    for n in sorted(requires):
        if not state.get(n):
            visit(n, [])
    if problems:
        raise RelationError("; ".join(problems))


def _shared(a: dict[str, Any] | None, b: dict[str, Any] | None) -> str:
    """Name what two similar items have in common, so the hint can be checked."""
    if not a or not b:
        return "shares tags or name words"
    structural = {a["kind"], b["kind"], a["namespace"], b["namespace"], "executes-code"}
    tags = sorted((set(a.get("tags", [])) & set(b.get("tags", []))) - structural)
    words = sorted(set(a["name"].split("-")) & set(b["name"].split("-")))
    parts = ([f"tags: {', '.join(tags)}"] if tags else []) + (
        [f"name words: {', '.join(words)}"] if words else []
    )
    return "shares " + "; ".join(parts) if parts else "shares tags or name words"


def build(
    items: list[dict[str, Any]],
    ledger: dict[str, Any],
    similar: dict[str, list[str]] | None = None,
    curated: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """``{"items": {key: [{type, target, origin, evidence}]}}``, deterministic, one entry per (type, target)."""
    keys = {releases.key_of(it) for it in items}
    curated = applicable(load_curated() if curated is None else curated, keys)
    _check_curated(curated, keys)
    out: dict[str, dict[tuple[str, str], dict[str, str]]] = {k: {} for k in keys}

    def add(src: str, typ: str, dst: str, origin: str, evidence: str) -> None:
        if src not in keys or dst not in keys or src == dst:
            return  # derived facts about items no longer in the trove are not shown (never dangling)
        slot = out[src]
        cur = slot.get((typ, dst))
        if cur is None or ORIGIN_RANK[origin] < ORIGIN_RANK[cur["origin"]]:
            slot[(typ, dst)] = {"type": typ, "target": dst, "origin": origin, "evidence": evidence}

    for r in curated:
        a, t, b, ev = r["from"], r["type"], r["to"], r["evidence"]
        add(a, t, b, "curated", ev)
        add(b, t if t in SYMMETRIC else INVERSE[t], a, "curated", ev)
    for it in items:
        key = releases.key_of(it)
        for member in it.get("members", []):
            add(member, "part-of", key, "derived", "plugin.json lists it as a member")
            add(key, "bundles", member, "derived", "plugin.json lists it as a member")
    for key, entry in ledger.get("items", {}).items():
        rels = entry.get("releases", [])
        parent = next((r["parent"] for r in reversed(rels) if r.get("parent")), None)
        if parent:
            ev = f"release ledger: forked from {parent['key']}@{parent['version']}"
            add(key, "forked-from", parent["key"], "derived", ev)
            add(parent["key"], "forked-as", key, "derived", ev)
        dep = (rels[-1].get("deprecated") or {}) if rels else {}
        if dep.get("replaced_by"):
            add(key, "replaced-by", dep["replaced_by"], "derived", f"deprecated: {dep['reason']}")
            add(dep["replaced_by"], "replaces", key, "derived", f"deprecated: {dep['reason']}")
    by_key = {releases.key_of(it): it for it in items}
    for key, others in (similar or {}).items():
        typed = {t for (_, t) in out.get(key, {})}
        for other in others:
            if other not in typed:
                add(key, "similar", other, "inferred", _shared(by_key.get(key), by_key.get(other)))
    order = {t: i for i, t in enumerate(TYPES)}
    return {
        "items": {
            k: sorted(v.values(), key=lambda r: (order[r["type"]], ORIGIN_RANK[r["origin"]], r["target"]))
            for k, v in sorted(out.items())
            if v
        }
    }


def write(trove: Path, data: dict[str, Any]) -> None:
    (trove / RELATIONS_FILE).write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def load(trove: Path) -> dict[str, Any]:
    path = trove / RELATIONS_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"items": {}}


__all__ = ["RELATIONS_FILE", "TYPES", "RelationError", "build", "load", "load_curated", "write"]
