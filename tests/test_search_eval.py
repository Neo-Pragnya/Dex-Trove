"""The optional semantic ranker must beat the lexical baseline on real questions (ASM-D10).

The labelled set is tests/fixtures/search_eval.json, run against the real trove. Numbers when written: lexical
recall@10 0.04, semantic 0.67 (MRR 0.04 → 0.50). The thresholds leave room for trove refreshes.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from dex_trove import catalog, semantic
from dex_trove.cli import app

EVAL = json.loads((Path(__file__).parent / "fixtures" / "search_eval.json").read_text())


def recall_at_10(rank) -> float:  # type: ignore[no-untyped-def]
    hits = 0
    for q in EVAL["queries"]:
        got = [f"{i['kind']}:{i['id']}" for i in rank(q["q"])][:10]
        hits += any(r in got for r in q["relevant"])
    return hits / len(EVAL["queries"])


def test_semantic_beats_the_lexical_baseline() -> None:
    items = catalog.load()
    ids = {f"{i['kind']}:{i['id']}" for i in items}
    assert all(r in ids for q in EVAL["queries"] for r in q["relevant"]), (
        "eval set names an item not in the trove"
    )
    lexical = recall_at_10(lambda q: catalog.search(items, q))
    smart = recall_at_10(lambda q: semantic.rank(items, q))
    assert smart >= 0.55 and smart >= lexical + 0.4, (lexical, smart)


def test_semantic_is_offline_and_reorders_only_existing_items() -> None:
    items = catalog.load()
    out = semantic.rank(items, "write the failing test before the code")
    assert out and all(i in items for i in out)
    assert semantic.stem("testing") == semantic.stem("tests") == "test"


def test_search_rank_option() -> None:
    runner = CliRunner()
    res = runner.invoke(
        app, ["search", "find", "the", "root", "cause", "of", "a", "bug", "--rank", "semantic", "--json"]
    )
    assert res.exit_code == 0 and json.loads(res.stdout)
    assert runner.invoke(app, ["search", "x", "--rank", "magic"]).exit_code == 2
