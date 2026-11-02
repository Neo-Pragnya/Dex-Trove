from __future__ import annotations

from pathlib import Path

import pytest

from dex_trove import catalog, learn, relations, releases
from dex_trove.sources import Source


def built(trove: Path, source: Source, upstream: Path, curated: list[dict[str, str]]) -> dict:
    result = learn.Learner(trove).learn(source, upstream, "abc123", {source.id: 0})
    learn.finalize(trove, [result], [source])
    items = catalog.load(trove)
    return relations.build(
        items, releases.load(trove), {"skill:up/alpha": ["skill:up/runner", "skill:up/fonts"]}, curated
    )


def rel(src: str, typ: str, dst: str, evidence: str = "SKILL.md says so") -> dict[str, str]:
    return {"from": src, "type": typ, "to": dst, "evidence": evidence}


def of(data: dict, key: str) -> set[tuple[str, str, str]]:
    return {(r["type"], r["target"], r["origin"]) for r in data["items"].get(key, [])}


def test_types_inverses_and_origins(trove: Path, source: Source, upstream: Path) -> None:
    data = built(
        trove,
        source,
        upstream,
        [
            rel("skill:up/alpha", "requires", "skill:up/runner"),
            rel("skill:up/alpha", "alternative-to", "skill:up/apache-declared"),
        ],
    )
    alpha = of(data, "skill:up/alpha")
    assert ("requires", "skill:up/runner", "curated") in alpha
    assert ("alternative-to", "skill:up/apache-declared", "curated") in alpha
    assert ("part-of", "plugin:up/kit", "derived") in alpha
    # an inferred `similar` hint is dropped when a typed relation already links the pair
    assert ("similar", "skill:up/runner", "inferred") not in alpha
    assert ("similar", "skill:up/fonts", "inferred") in alpha
    assert ("required-by", "skill:up/alpha", "curated") in of(data, "skill:up/runner")
    assert ("alternative-to", "skill:up/alpha", "curated") in of(data, "skill:up/apache-declared")
    assert ("bundles", "skill:up/alpha", "derived") in of(data, "plugin:up/kit")


def test_no_relation_type_claims_compatibility() -> None:
    assert not any("compat" in t for t in relations.TYPES)


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (rel("skill:up/alpha", "requires", "skill:up/missing"), "is not a trove item"),
        (rel("skill:up/alpha", "compatible-with", "skill:up/runner"), "type must be one of"),
        (rel("skill:up/alpha", "complements", "skill:up/runner", evidence=" "), "evidence is required"),
        (rel("skill:up/alpha", "complements", "skill:up/alpha"), "relate to itself"),
    ],
)
def test_curated_relations_are_checked(
    trove: Path, source: Source, upstream: Path, entry: dict, message: str
) -> None:
    with pytest.raises(relations.RelationError, match=message):
        built(trove, source, upstream, [entry])


def test_requires_cycles_are_rejected(trove: Path, source: Source, upstream: Path) -> None:
    with pytest.raises(relations.RelationError, match="requires cycle"):
        built(
            trove,
            source,
            upstream,
            [
                rel("skill:up/alpha", "requires", "skill:up/runner"),
                rel("skill:up/runner", "requires", "skill:up/alpha"),
            ],
        )


def test_relations_about_sources_this_trove_lacks_are_skipped(
    trove: Path, source: Source, upstream: Path
) -> None:
    data = built(trove, source, upstream, [rel("skill:elsewhere/a", "complements", "skill:elsewhere/b")])
    assert "skill:elsewhere/a" not in data["items"]


def test_deprecation_becomes_replaced_by(trove: Path, source: Source, upstream: Path) -> None:
    built(trove, source, upstream, [])
    ledger = releases.load(trove)
    releases.deprecate(ledger, "skill:up/runner", "merged into alpha", at="x", replaced_by="skill:up/alpha")
    data = relations.build(catalog.load(trove), ledger, {}, [])
    assert ("replaced-by", "skill:up/alpha", "derived") in of(data, "skill:up/runner")
    assert ("replaces", "skill:up/runner", "derived") in of(data, "skill:up/alpha")
