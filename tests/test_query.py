"""Faceted search semantics: golden cases on a small synthetic trove (no real catalog involved)."""

from __future__ import annotations

from typing import Any

import pytest

from dex_trove import facets, query, taxonomy
from dex_trove.query import FacetQuery, QueryError


def _item(name: str, **facet_values: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    item = {
        "kind": "skill",
        "id": f"t/{name}",
        "namespace": "t",
        "name": name,
        "title": name,
        "description": name,
    }
    approved = facet_values.pop("approved", False)
    rec = {
        "facets": {"kind": "skill", **facet_values},
        "classification": {"review_status": "approved" if approved else "review-pending"},
    }
    return item, rec


FIXTURE = [
    _item(
        "api-tests",
        task=["generate-api-tests", "write-tests"],
        methodology=["adlc", "tdd"],
        role=["qa-engineer"],
        language=["python"],
        approved=True,
    ),
    _item(
        "api-review",
        task=["review-code"],
        methodology=["sdlc"],
        role=["developer", "reviewer"],
        language=["python"],
    ),
    _item(
        "ts-tests", task=["write-tests"], methodology=["sdlc"], role=["qa-engineer"], language=["typescript"]
    ),
    _item("no-method", task=["write-tests"], role=["qa-engineer"], language=["python"]),
    _item(
        "old-tests",
        task=["write-tests"],
        methodology=["adlc"],
        role=["qa-engineer"],
        language=["python"],
        maturity="deprecated",
    ),
]
ITEMS = [i for i, _ in FIXTURE]
RECORDS = {facets.item_key(i): r for i, r in FIXTURE}


def _run(**kw: Any) -> query.QueryResult:
    return query.run(FacetQuery(**kw), taxonomy.load(), items=ITEMS, records=RECORDS)


def _ids(result: query.QueryResult) -> list[str]:
    return [h.item["name"] for h in result.hits]


def test_and_across_facets_or_within_a_facet() -> None:
    r = _run(all={"role": ["qa-engineer"], "language": ["python", "typescript"]})
    assert set(_ids(r)) == {"api-tests", "ts-tests", "no-method", "old-tests"}
    r = _run(all={"role": ["qa-engineer"], "language": ["typescript"]})
    assert _ids(r) == ["ts-tests"]


def test_missing_metadata_never_matches() -> None:
    assert "no-method" not in _ids(_run(all={"methodology": ["adlc", "sdlc"]}))


def test_exclusions_remove_items() -> None:
    r = _run(all={"methodology": ["adlc"]}, exclude={"maturity": ["deprecated"]})
    assert _ids(r) == ["api-tests"]


def test_strict_requires_every_value_within_a_facet() -> None:
    assert set(_ids(_run(all={"task": ["write-tests", "generate-api-tests"]}))) == {
        "api-tests",
        "ts-tests",
        "no-method",
        "old-tests",
    }
    assert _ids(_run(all={"task": ["write-tests", "generate-api-tests"]}, strict=True)) == ["api-tests"]


def test_aliases_normalise_and_unknown_values_are_errors_not_ignored() -> None:
    assert _ids(_run(all={"role": ["test-engineer"], "task": ["api-tests"]})) == ["api-tests"]
    with pytest.raises(QueryError, match="not a methodology term"):
        _run(all={"methodology": ["waterfall"]})
    with pytest.raises(QueryError, match="unknown facet"):
        _run(all={"colour": ["blue"]})


def test_ranking_prefers_fuller_matches_then_curated_then_id() -> None:
    r = _run(all={"methodology": ["adlc"], "task": ["generate-api-tests", "write-tests"]})
    assert _ids(r)[0] == "api-tests"  # matches both tasks and is curated
    assert r.hits[0].matched == {"methodology": ["adlc"], "task": ["generate-api-tests", "write-tests"]}
    assert r.hits[0].contributions["curated"] == pytest.approx(0.10)


def test_facet_counts_are_disjunctive() -> None:
    r = _run(all={"language": ["typescript"]})
    # The language counts ignore the language selection, so they say what choosing python would add.
    assert r.facet_counts["language"] == {"python": 4, "typescript": 1}
    assert r.facet_counts["role"] == {"qa-engineer": 1}


def test_pagination_is_stable_and_complete() -> None:
    first = _run(all={"role": ["qa-engineer"]}, limit=2)
    second = _run(all={"role": ["qa-engineer"]}, limit=2, cursor=first.next_cursor)
    everything = _run(all={"role": ["qa-engineer"]}, limit=10)
    assert _ids(first) + _ids(second) == _ids(everything)[:4]
    assert second.next_cursor is None and first.total == 4
    with pytest.raises(QueryError, match="cursor"):
        _run(cursor="abc")


def test_empty_results_explain_which_filter_to_drop_and_never_relax_silently() -> None:
    r = _run(all={"language": ["typescript"], "methodology": ["adlc"]})
    assert r.hits == [] and r.total == 0
    assert r.relaxations == {"language": 2, "methodology": 1}


def test_text_and_facets_combine() -> None:
    assert _ids(_run(text="review", all={"language": ["python"]})) == ["api-review"]
