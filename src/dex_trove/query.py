"""Faceted search over the trove (docs/guides/finding-capabilities.md).

Semantics, deliberately boring and explainable:

- **OR within a dimension, AND across dimensions.** ``--language python --language typescript --role qa-engineer``
  means (python OR typescript) AND qa-engineer. ``strict`` requires every listed value of a dimension instead.
- **Exclusions** (``--not maturity=deprecated``) remove any item carrying an excluded value.
- **Missing metadata never matches.** An item with no ``methodology`` facet is not returned for
  ``--methodology adlc``; ``facet_counts`` show how many items have the dimension at all.
- **Filter first, rank second.** Ranking orders the eligible items; it never adds an item a filter excluded and
  never relaxes a filter. An empty result reports which single filter, if dropped, would give results.
- **Counts are disjunctive**: each dimension's value counts ignore that dimension's own selection, so the numbers
  next to a filter say what choosing it would add.

Tags and facets describe relevance. They do not prove an item will run in your harness: typed inputs and outputs,
declared requirements, installed tools and policy decide that (Ananke resolves and checks those).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from dex_trove import catalog, facets
from dex_trove.taxonomy import Taxonomy, TaxonomyError

# Initial ranking weights from the taxonomy design (tuning knobs, not measured truths).
WEIGHTS = {"task": 0.30, "methodology": 0.20, "phase": 0.15, "role": 0.10, "context": 0.10, "curated": 0.10}
CONTEXT_DIMENSIONS = ("domain", "language", "framework", "platform")
MULTI = ("task", "methodology", "phase", "role", "domain", "language", "framework", "platform")


class QueryError(ValueError):
    pass


@dataclass
class FacetQuery:
    text: str = ""
    all: dict[str, list[str]] = field(default_factory=dict)
    exclude: dict[str, list[str]] = field(default_factory=dict)
    strict: bool = False
    limit: int = 20
    cursor: str | None = None


@dataclass
class Hit:
    key: str
    item: dict[str, Any]
    facets: dict[str, Any]
    score: float
    matched: dict[str, list[str]]
    contributions: dict[str, float]
    review_status: str


@dataclass
class QueryResult:
    total: int
    hits: list[Hit]
    next_cursor: str | None
    facet_counts: dict[str, dict[str, int]]
    query: dict[str, Any]
    relaxations: dict[str, int] = field(default_factory=dict)


def _values(rec: dict[str, Any], dim: str) -> set[str]:
    v = rec.get("facets", {}).get(dim)
    if v is None:
        return set()
    return {v} if isinstance(v, str) else set(v)


def normalize_filters(tax: Taxonomy, raw: dict[str, list[str]]) -> dict[str, list[str]]:
    """Canonical term ids; an unknown dimension or value is an error naming the valid choices, never ignored."""
    out: dict[str, list[str]] = {}
    for dim, values in raw.items():
        if not values:
            continue
        if dim not in tax.dimensions:
            raise QueryError(f"unknown facet {dim!r}; facets: {', '.join(tax.dimensions)}")
        canon = []
        for value in values:
            term = tax.normalize(dim, value)
            if term is None:
                choices = ", ".join(sorted(tax.dimensions[dim].terms))
                raise QueryError(f"{value!r} is not a {dim} term; choose from: {choices}")
            if term not in canon:
                canon.append(term)
        out[dim] = canon
    return out


def parse_exclusions(specs: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for spec in specs:
        if "=" not in spec:
            raise QueryError(f"--not expects facet=value, got {spec!r}")
        dim, value = (s.strip() for s in spec.split("=", 1))
        out.setdefault(dim, []).append(value)
    return out


def _passes(
    rec: dict[str, Any], filters: dict[str, list[str]], strict: bool, skip: str | None = None
) -> bool:
    for dim, wanted in filters.items():
        if dim == skip:
            continue
        have = _values(rec, dim)
        if strict and not set(wanted) <= have:
            return False
        if not strict and not have & set(wanted):
            return False
    return True


def _excluded(rec: dict[str, Any], exclude: dict[str, list[str]]) -> bool:
    return any(_values(rec, dim) & set(vals) for dim, vals in exclude.items())


def _score(
    rec: dict[str, Any], filters: dict[str, list[str]]
) -> tuple[float, dict[str, float], dict[str, list[str]]]:
    parts: dict[str, float] = {}
    matched: dict[str, list[str]] = {}
    for dim, wanted in filters.items():
        hit = sorted(_values(rec, dim) & set(wanted))
        if hit:
            matched[dim] = hit
        share = len(hit) / len(wanted)
        group = "context" if dim in CONTEXT_DIMENSIONS else dim
        if group in WEIGHTS:
            parts[group] = max(parts.get(group, 0.0), share)
    approved = rec.get("classification", {}).get("review_status") == "approved"
    parts["curated"] = 1.0 if approved else 0.5
    total_weight = sum(WEIGHTS[g] for g in parts)
    contributions = {g: round(WEIGHTS[g] * v, 4) for g, v in parts.items()}
    score = sum(WEIGHTS[g] * v for g, v in parts.items()) / total_weight if total_weight else 0.0
    return round(score, 4), contributions, matched


def run(
    q: FacetQuery,
    tax: Taxonomy,
    items: list[dict[str, Any]] | None = None,
    records: dict[str, dict[str, Any]] | None = None,
) -> QueryResult:
    items = catalog.load() if items is None else items
    if records is None:
        records = facets.load()
    if not records:  # a trove built before facets.json existed (or a test's own items)
        records = facets.build(items, tax, check_stale=False)["items"]
    try:
        filters = normalize_filters(tax, q.all)
        exclude = normalize_filters(tax, q.exclude)
    except TaxonomyError as exc:  # an unknown dimension inside the taxonomy layer
        raise QueryError(str(exc)) from exc

    pool = items
    lexical: dict[str, int] = {}
    if q.text.strip():
        ranked = catalog.search(items, q.text)
        lexical = {facets.item_key(it): len(ranked) - i for i, it in enumerate(ranked)}
        pool = ranked
    base = []
    for it in pool:
        key = facets.item_key(it)
        rec = records.get(key)
        if rec is None or _excluded(rec, exclude):
            continue
        base.append((key, it, rec))

    eligible = [(k, it, rec) for k, it, rec in base if _passes(rec, filters, q.strict)]
    hits = []
    for key, it, rec in eligible:
        score, contributions, matched = _score(rec, filters)
        hits.append(
            Hit(key, it, rec["facets"], score, matched, contributions, rec["classification"]["review_status"])
        )
    hits.sort(key=lambda h: (-h.score, -lexical.get(h.key, 0), h.key))

    counts: dict[str, dict[str, int]] = {}
    for dim in MULTI + ("kind", "maturity"):
        if dim not in tax.dimensions:
            continue
        c: Counter[str] = Counter()
        for _key, _it, rec in base:
            if _passes(rec, filters, q.strict, skip=dim):
                c.update(_values(rec, dim))
        counts[dim] = dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))

    relaxations: dict[str, int] = {}
    if not hits and filters:
        for dim in filters:
            relaxations[dim] = sum(1 for _k, _i, rec in base if _passes(rec, filters, q.strict, skip=dim))

    try:
        offset = int(q.cursor) if q.cursor else 0
    except ValueError as exc:
        raise QueryError(f"invalid cursor {q.cursor!r}") from exc
    if offset < 0:
        raise QueryError("cursor must be a non-negative offset")
    page = hits[offset : offset + q.limit]
    nxt = str(offset + q.limit) if offset + q.limit < len(hits) else None
    echo = {
        "text": q.text,
        "all": filters,
        "not": exclude,
        "strict": q.strict,
        "taxonomy_version": tax.version,
    }
    return QueryResult(len(hits), page, nxt, counts, echo, relaxations)


def to_json(result: QueryResult, *, explain: bool) -> dict[str, Any]:
    rows = []
    for h in result.hits:
        row: dict[str, Any] = {
            "kind": h.item["kind"],
            "id": h.item["id"],
            "title": h.item["title"],
            "description": h.item["description"],
            "facets": h.facets,
            "score": h.score,
        }
        if explain:
            row["why"] = {
                "matched": h.matched,
                "contributions": h.contributions,
                "review_status": h.review_status,
            }
        rows.append(row)
    return {
        "query": result.query,
        "total": result.total,
        "next_cursor": result.next_cursor,
        "results": rows,
        "facet_counts": result.facet_counts,
        "relaxations": result.relaxations,
    }


__all__ = [
    "FacetQuery",
    "Hit",
    "QueryError",
    "QueryResult",
    "normalize_filters",
    "parse_exclusions",
    "run",
    "to_json",
]
