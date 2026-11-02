"""The taxonomy is data with strict rules: stable ids, unambiguous aliases, SDLC and ADLC kept distinct."""

from __future__ import annotations

from typing import Any

import pytest

from dex_trove import taxonomy
from dex_trove.taxonomy import TaxonomyError


def _tax(**task_terms: Any) -> dict[str, Any]:
    return {
        "taxonomy_version": "1.0.0",
        "dimensions": {
            "kind": {"cardinality": "one", "terms": [{"id": "skill", "definition": "x"}]},
            "task": {"cardinality": "many", "terms": list(task_terms.values())},
        },
    }


def test_shipped_taxonomy_is_valid_and_keeps_sdlc_and_adlc_apart() -> None:
    tax = taxonomy.load()
    assert tax.version.count(".") == 2
    assert tax.normalize("methodology", "sdlc") == "sdlc"
    assert tax.normalize("methodology", "ADLC") == "adlc"
    assert tax.normalize("methodology", "agent-development-lifecycle") == "adlc"
    assert tax.normalize("methodology", "sdlc") != tax.normalize("methodology", "adlc")
    assert tax.normalize("role", "Test Engineer") == "qa-engineer"  # alias, case and spaces normalised
    assert tax.normalize("task", "no-such-task") is None  # unknown is reported, not guessed
    for dim in tax.dimensions.values():
        for term in dim.terms.values():
            assert term.definition, f"{dim.id}/{term.id} needs a definition"


def test_every_curated_value_is_a_known_term() -> None:
    tax = taxonomy.load()
    for ref, entry in taxonomy.load_curation().items():
        for dim, values in entry.items():
            if dim in ("evidence", "notes"):
                continue
            for value in values if isinstance(values, list) else [values]:
                assert tax.normalize(dim, value), f"{ref}: {dim}={value}"


def test_unknown_dimension_is_an_error() -> None:
    with pytest.raises(TaxonomyError, match="unknown dimension"):
        taxonomy.load().normalize("colour", "blue")


def test_duplicate_term_id_is_rejected() -> None:
    data = _tax(a={"id": "review-code", "definition": "x"}, b={"id": "review-code", "definition": "y"})
    with pytest.raises(TaxonomyError, match="duplicate term id"):
        taxonomy.parse(data)


def test_an_alias_cannot_name_two_terms() -> None:
    data = _tax(
        a={"id": "review-code", "definition": "x", "aliases": ["review"]},
        b={"id": "security-review", "definition": "y", "aliases": ["review"]},
    )
    with pytest.raises(TaxonomyError, match="names both"):
        taxonomy.parse(data)


def test_sdlc_and_adlc_cannot_be_made_aliases() -> None:
    data = _tax()
    data["dimensions"]["methodology"] = {
        "cardinality": "many",
        "terms": [{"id": "sdlc", "definition": "x", "aliases": ["adlc"]}, {"id": "adlc", "definition": "y"}],
    }
    with pytest.raises(TaxonomyError):
        taxonomy.parse(data)


def test_deprecated_term_migrates_to_its_replacement() -> None:
    data = _tax(
        old={"id": "triage-ci", "definition": "x", "deprecated": True, "replaced_by": "debug-ci"},
        new={"id": "debug-ci", "definition": "y"},
    )
    assert taxonomy.parse(data).normalize("task", "triage-ci") == "debug-ci"
    data["dimensions"]["task"]["terms"][0]["replaced_by"] = "nowhere"
    with pytest.raises(TaxonomyError, match="replaced_by"):
        taxonomy.parse(data)


def test_bad_ids_versions_and_patterns_are_rejected() -> None:
    with pytest.raises(TaxonomyError, match="lower-kebab"):
        taxonomy.parse(_tax(a={"id": "Review Code", "definition": "x"}))
    with pytest.raises(TaxonomyError, match="definition"):
        taxonomy.parse(_tax(a={"id": "review-code"}))
    with pytest.raises(TaxonomyError, match="bad match pattern"):
        taxonomy.parse(_tax(a={"id": "review-code", "definition": "x", "match": ["(unclosed"]}))
    bad = _tax()
    bad["taxonomy_version"] = "1"
    with pytest.raises(TaxonomyError, match="MAJOR.MINOR.PATCH"):
        taxonomy.parse(bad)
