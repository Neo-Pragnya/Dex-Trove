"""The facet sidecar: precedence, provenance, idempotence, and rule precision on real phrasing."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from dex_trove import facets, learn, taxonomy
from dex_trove.sources import Source


def _item(name: str, description: str, kind: str = "skill", **extra: Any) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": f"t/{name}",
        "namespace": "t",
        "name": name,
        "title": name,
        "description": description,
        "tags": extra.pop("tags", []),
        "version": "1.0.0",
        **extra,
    }


def _facets(item: dict[str, Any], curation: dict[str, Any] | None = None) -> dict[str, Any]:
    return facets.classify(item, taxonomy.load(), curation or {})


@pytest.mark.parametrize(
    ("description", "dimension", "term", "expected"),
    [
        # documentation: authoring docs, not mentioning that docs exist
        (
            "Generates professional MS Word project documentation with draw.io diagrams",
            "task",
            "write-docs",
            True,
        ),
        ("Create or update standardized object-oriented component documentation", "task", "write-docs", True),
        ("Ensure that Java types are documented with Javadoc comments", "task", "write-docs", True),
        (
            "Playwright Python AI test generation instructions based on official documentation",
            "task",
            "write-docs",
            False,
        ),
        (
            "Query official Microsoft documentation to find concepts, tutorials, and code examples",
            "task",
            "write-docs",
            False,
        ),
        # ml-ai: building AI systems, not text that mentions AI
        ("Detect and remove AI-generated markers from Finnish text", "domain", "ml-ai", False),
        ("Build agents with the Microsoft Foundry SDK in Python", "domain", "ml-ai", True),
        # build-agents: making agents, skills or MCP servers, not using them
        (
            "Use this skill when the user asks to create a poster or piece of art",
            "task",
            "build-agents",
            False,
        ),
        ("Instructions for building MCP servers in Go", "task", "build-agents", True),
        # implement: an implementation *plan* is planning
        ("Generate an implementation plan for new features", "task", "implement", False),
        ("Generate an implementation plan for new features", "task", "write-spec", True),
    ],
)
def test_rule_precision_on_real_phrasing(description: str, dimension: str, term: str, expected: bool) -> None:
    got = _facets(_item("x", description))["facets"].get(dimension) or []
    assert (term in got) is expected, f"{dimension}={got}"


def test_rule_values_carry_evidence_and_stay_pending() -> None:
    rec = _facets(_item("pytest-coverage", "Run pytest tests with coverage"))
    assert rec["classification"] == {"source": "rules", "review_status": "review-pending"}
    assert "pytest" in rec["facets"]["framework"]
    assert rec["provenance"]["framework"]["evidence"]["pytest"][0].startswith(("name:", "description:"))


def test_curation_wins_per_dimension_and_keeps_what_it_overrode() -> None:
    item = _item("tdd", "Write tests first with pytest", tags=["python"])
    rec = _facets(item, {"t/tdd": {"task": ["write-tests"], "methodology": ["tdd"], "evidence": "reviewed"}})
    assert rec["classification"] == {"source": "curated", "review_status": "approved"}
    assert rec["facets"]["methodology"] == ["tdd"]
    assert rec["provenance"]["task"]["source"] == "curated"
    assert "rules" in rec["provenance"]["task"].get("also_suggested", {})
    assert rec["facets"]["language"] == ["python"]  # not curated, so the upstream tag still counts
    assert rec["provenance"]["language"]["source"] == "native"


def test_native_metadata_beats_rules() -> None:
    rec = _facets(_item("go-style", "Conventions", kind="instruction", apply_to="**/*.go, **/*.mod"))
    assert rec["facets"]["language"] == ["go"]
    assert rec["provenance"]["language"]["evidence"]["go"] == ["applyTo: '**/*.go'"]


def test_unmapped_tags_are_kept_for_review() -> None:
    rec = _facets(_item("x", "d", tags=["python", "frobnication"]))
    assert rec["unmapped"] == {"tags": ["frobnication"]}


def test_curation_with_an_unknown_value_is_an_error() -> None:
    with pytest.raises(taxonomy.TaxonomyError, match="not a methodology term"):
        _facets(_item("x", "d"), {"t/x": {"methodology": ["waterfall"]}})


def test_platform_comes_from_the_install_layout() -> None:
    assert _facets(_item("x", "d", kind="instruction"))["facets"]["platform"] == ["ananke", "github-copilot"]
    assert "claude-code" in _facets(_item("x", "d", kind="agent"))["facets"]["platform"]


def test_learning_writes_facets_without_touching_upstream_bytes(
    trove: Path, source: Source, upstream: Path
) -> None:
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in upstream.rglob("*") if p.is_file()}
    result = learn.Learner(trove).learn(source, upstream, "abc", {source.id: 0})
    learn.finalize(trove, [result], [source])
    first = (trove / facets.FACETS_FILE).read_text()
    learn.finalize(trove, [result], [source])
    assert (trove / facets.FACETS_FILE).read_text() == first  # deterministic, no timestamps
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in upstream.rglob("*") if p.is_file()}
    assert before == after
    item_files = [p.name for p in trove.rglob("*") if p.is_file() and p.parent != trove]
    assert facets.FACETS_FILE not in item_files  # the sidecar lives beside catalog.json, never in an item
    assert facets.load(trove)
