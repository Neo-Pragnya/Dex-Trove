from __future__ import annotations

from dex_trove import overlap


def item(name: str, description: str, *, runs: bool = False) -> dict:
    return {
        "kind": "skill",
        "id": f"x/{name}",
        "name": name,
        "title": name,
        "description": description,
        "executes_code": runs,
        "license": {"evidence": "LICENSE: MIT"},
    }


def test_similarity_and_scoring_use_only_verifiable_signals() -> None:
    a = item("web-test", "Test local web applications with Playwright: screenshots, logs and UI checks.")
    b = item(
        "webapp-testing",
        "Test local web applications using Playwright, with screenshots, logs and UI checks.",
        runs=True,
    )
    c = item("csv-report", "Summarise a CSV file into totals and outliers.")
    assert overlap.jaccard(overlap.words(a), overlap.words(b)) > 0.45
    assert overlap.jaccard(overlap.words(a), overlap.words(c)) < 0.1
    reviewed = {"classification": {"review_status": "approved"}}
    sa, why_a = overlap.score(a, reviewed, {"claude": "pass", "copilot": "pass"})
    sb, why_b = overlap.score(b, {}, {"claude": "fail: x"})
    assert sa > sb
    assert (
        "install checks pass" in why_a
        and "an install check fails" in why_b
        and "bundles code to review" in why_b
    )
