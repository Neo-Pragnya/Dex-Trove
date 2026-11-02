"""Derived facet sidecar: ``trove/facets.json`` (docs/guides/finding-capabilities.md).

Upstream files are never edited. Facets are computed from four sources and every value keeps where it came from:

1. ``curated``: ``taxonomy/curation.yaml``, reviewed by a person (``approved``).
2. ``native``: the item's own metadata: upstream tags, and ``applyTo`` globs for instructions.
3. ``rules``: the taxonomy's ``match`` patterns over name, title, description and tags (``review-pending``).
4. ``derived``: facts Dex knows itself: ``kind`` from the catalog, ``platform`` from the install layout.

For each dimension the first source in that order with any value wins; the others stay in ``provenance`` so a
reviewer can see what was overridden. The build is deterministic (no timestamps), so re-running it on an unchanged
trove changes nothing.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any

from dex_trove import taxonomy
from dex_trove.taxonomy import Taxonomy

SCHEMA_VERSION = "1.0.0"
FACETS_FILE = "facets.json"
PRECEDENCE = ("curated", "native", "rules")
RULE_DIMENSIONS = ("task", "methodology", "phase", "role", "domain", "language", "framework")
# Upstream tags are author-supplied but loose; only map them where a tag reliably means the same thing.
TAG_DIMENSIONS = ("task", "methodology", "domain", "language", "framework")
STRUCTURAL_TAGS = {"executes-code", "skill", "agent", "instruction", "prompt", "workflow", "hook", "plugin"}
# Where `dex install` (and `dex ananke sync`) can place each kind natively (install.py, ananke_bridge.py).
PLATFORMS = {
    "claude-code": {"skill", "agent", "prompt", "plugin"},
    "github-copilot": {"skill", "agent", "instruction", "prompt", "hook", "workflow", "plugin"},
    "ananke": {"skill", "agent", "instruction", "prompt", "hook", "workflow", "plugin"},
}


def item_key(item: dict[str, Any]) -> str:
    return f"{item['kind']}:{item['id']}"


def _text_fields(item: dict[str, Any]) -> list[tuple[str, str]]:
    tags = [t for t in item.get("tags", []) if t not in STRUCTURAL_TAGS and t != item.get("namespace")]
    return [
        ("name", str(item.get("name", "")).replace("-", " ")),
        ("title", str(item.get("title", ""))),
        ("description", str(item.get("description", ""))),
        ("tags", " ".join(tags)),
    ]


def _rules(tax: Taxonomy, item: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    """``{dimension: {term: [evidence, ...]}}`` from match patterns."""
    out: dict[str, dict[str, list[str]]] = {}
    fields = _text_fields(item)
    for dim_id in RULE_DIMENSIONS:
        dim = tax.dimensions.get(dim_id)
        if dim is None:
            continue
        for term in dim.terms.values():
            if term.deprecated:
                continue
            for pattern in term.match:
                hit = next(((f, m) for f, text in fields if (m := pattern.search(text))), None)
                if hit:
                    field, m = hit
                    out.setdefault(dim_id, {})[term.id] = [f"{field}: {m.group(0)!r}"]
                    break
    return out


def _native(tax: Taxonomy, item: dict[str, Any]) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
    out: dict[str, dict[str, list[str]]] = {}
    unmapped: list[str] = []
    for tag in item.get("tags", []):
        if tag in STRUCTURAL_TAGS or tag == item.get("namespace"):
            continue
        hits = [(d, tax.normalize(d, tag)) for d in TAG_DIMENSIONS if d in tax.dimensions]
        hits = [(d, t) for d, t in hits if t]
        if not hits:
            unmapped.append(tag)
        for d, t in hits:
            out.setdefault(d, {}).setdefault(str(t), []).append(f"tag: {tag!r}")
    apply_to = item.get("apply_to")
    if apply_to and "language" in tax.dimensions:
        for glob in [g.strip() for g in str(apply_to).split(",") if g.strip()]:
            name = glob.rsplit("/", 1)[-1]
            for term in tax.dimensions["language"].terms.values():
                if any(fnmatch.fnmatch(name, g) or name == g for g in term.globs):
                    out.setdefault("language", {}).setdefault(term.id, []).append(f"applyTo: {glob!r}")
    return out, sorted(set(unmapped))


def _curated(tax: Taxonomy, entry: dict[str, Any], ref: str) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    evidence = str(entry.get("evidence") or "curation.yaml")
    for dim_id, values in entry.items():
        if dim_id in ("evidence", "notes"):
            continue
        if dim_id not in tax.dimensions:
            raise taxonomy.TaxonomyError(f"curation.yaml {ref}: unknown dimension {dim_id!r}")
        for value in values if isinstance(values, list) else [values]:
            term = tax.normalize(dim_id, str(value))
            if term is None:
                raise taxonomy.TaxonomyError(f"curation.yaml {ref}: {value!r} is not a {dim_id} term")
            out.setdefault(dim_id, {})[term] = [f"curated: {evidence}"]
    return out


def classify(item: dict[str, Any], tax: Taxonomy, curation: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The facet sidecar record for one catalog item."""
    sources: dict[str, dict[str, dict[str, list[str]]]] = {}
    entry = curation.get(item_key(item)) or curation.get(item["id"])
    if entry:
        sources["curated"] = _curated(tax, entry, item["id"])
    sources["native"], unmapped = _native(tax, item)
    sources["rules"] = _rules(tax, item)

    facets: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    for dim_id, dim in tax.dimensions.items():
        if dim.derived:
            continue
        for src in PRECEDENCE:
            values = sources.get(src, {}).get(dim_id)
            if values:
                chosen = sorted(values)
                facets[dim_id] = chosen[0] if dim.cardinality == "one" else chosen
                provenance[dim_id] = {"source": src, "evidence": {v: values[v] for v in chosen}}
                overridden = {
                    s: sorted(sources[s][dim_id])
                    for s in PRECEDENCE
                    if s != src and sources.get(s, {}).get(dim_id)
                }
                if overridden:
                    provenance[dim_id]["also_suggested"] = overridden
                break
    facets["kind"] = item["kind"]
    facets["platform"] = sorted(p for p, kinds in PLATFORMS.items() if item["kind"] in kinds)
    facets.setdefault("maturity", "unknown")
    for derived in ("kind", "platform"):
        provenance[derived] = {
            "source": "derived",
            "evidence": {"catalog": ["kind" if derived == "kind" else "install layout"]},
        }
    if "maturity" not in provenance:
        provenance["maturity"] = {"source": "derived", "evidence": {"unknown": ["no maturity metadata"]}}

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_ref": f"{item['id']}@{item.get('version', '0')}",
        "taxonomy_version": tax.version,
        "facets": {d: facets[d] for d in tax.dimensions if d in facets},
        "classification": {
            "source": "curated" if entry else ("native" if sources["native"] else "rules"),
            "review_status": "approved" if entry else "review-pending",
        },
        "provenance": provenance,
    }
    if unmapped:
        record["unmapped"] = {"tags": unmapped}
    return record


def build(
    items: list[dict[str, Any]],
    tax: Taxonomy | None = None,
    curation: dict[str, dict[str, Any]] | None = None,
    *,
    check_stale: bool = True,
) -> dict[str, Any]:
    tax = tax or taxonomy.load()
    curation = taxonomy.load_curation() if curation is None else curation
    keys = {item_key(i) for i in items} | {i["id"] for i in items}
    stale = sorted(k for k in curation if k not in keys)
    if stale and check_stale:
        raise taxonomy.TaxonomyError(
            f"curation.yaml names items that aren't in the trove: {', '.join(stale)}"
        )
    records = {item_key(i): classify(i, tax, curation) for i in sorted(items, key=item_key)}
    return {
        "schema_version": SCHEMA_VERSION,
        "taxonomy_version": tax.version,
        "count": len(records),
        "items": records,
    }


def write(trove: Path, items: list[dict[str, Any]]) -> dict[str, Any]:
    data = build(items, check_stale=False)  # tests/test_packaging.py checks curation against the real trove
    (trove / FACETS_FILE).write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=False) + "\n")
    return data


def load(trove: Path | None = None) -> dict[str, dict[str, Any]]:
    """Facet records keyed by ``kind:id``; an older trove without facets.json yields ``{}``."""
    from dex_trove.paths import trove_root

    path = (trove or trove_root()) / FACETS_FILE
    if not path.is_file():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8")).get("items", {}))


__all__ = ["FACETS_FILE", "PRECEDENCE", "build", "classify", "item_key", "load", "write"]


def taxonomy_markdown(tax: Taxonomy | None = None, records: dict[str, dict[str, Any]] | None = None) -> str:
    """docs/reference/taxonomy.md, generated so the reference can't drift from ontology.yaml."""
    tax = tax or taxonomy.load()
    counts: dict[str, dict[str, int]] = {}
    for rec in (records or {}).values():
        for dim, value in rec["facets"].items():
            for v in [value] if isinstance(value, str) else value:
                counts.setdefault(dim, {}).setdefault(v, 0)
                counts[dim][v] += 1
    out = [
        "---",
        "title: Taxonomy reference",
        "description: Every facet and value Dex Trove uses to classify items, with definitions and aliases.",
        "---",
        "",
        "# Taxonomy reference",
        "",
        f"Taxonomy version **{tax.version}**. Generated from `src/dex_trove/taxonomy/ontology.yaml` by",
        "`dex facets doc`; don't edit by hand. How the facets are filled and queried:",
        "[Finding capabilities](../guides/finding-capabilities.md).",
        "",
        "Aliases are other spellings that mean the same value: `dex search --role test-engineer` is",
        "`--role qa-engineer`. Item counts are for the trove this page was generated with.",
    ]
    for dim in tax.dimensions.values():
        how = {
            "catalog": "Set from the catalog.",
            "install-layout": "Set from where `dex install` can place it.",
        }
        out += [
            "",
            f"## {dim.label} (`{dim.id}`)",
            "",
            f"{dim.question} "
            f"{'One value per item.' if dim.cardinality == 'one' else 'Any number of values.'} "
            f"{how.get(dim.derived or '', '')}".rstrip(),
            "",
            "| Value | Items | Definition | Aliases |",
            "| --- | --- | --- | --- |",
        ]
        for t in dim.terms.values():
            aliases = ", ".join(f"`{a}`" for a in t.aliases) or "—"
            n = counts.get(dim.id, {}).get(t.id, 0)
            out.append(f"| `{t.id}` | {n} | {t.definition.replace('|', '/')} | {aliases} |")
    return "\n".join(out) + "\n"
