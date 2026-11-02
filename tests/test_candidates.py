from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from dex_trove import candidates, catalog, learn, releases
from dex_trove.sources import Source

from .conftest import MIT

GPL = "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n"


def make(
    tmp: Path,
    name: str = "fix-flaky-tests",
    *,
    cases: list[dict] | None = None,
    license_text: str = MIT,
    extra: dict[str, str] | None = None,
) -> Path:
    d = tmp / "candidates" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Stabilise flaky tests by isolating time, randomness and order. Use when a test fails intermittently.\n---\n\n# {name}\n\nSteps.\n"
    )
    (d / "LICENSE").write_text(license_text)
    for rel, text in (extra or {}).items():
        (d / rel).write_text(text)
    evaluation = {
        "schema": "dex-trove/evaluation@1",
        "finished_at": "2026-11-02T00:00:00+00:00",
        "cases": cases
        if cases is not None
        else [
            {"id": "pos-1", "kind": "positive", "passed": True},
            {"id": "reg-1", "kind": "regression", "passed": True},
        ],
    }
    (d / "evaluation.json").write_text(json.dumps(evaluation))
    return d


def dest_source(tmp: Path, visibility: str = "public") -> Source:
    local = tmp / f"dest-{visibility}"
    local.mkdir(exist_ok=True)
    return Source(
        id=f"dest-{visibility}", title="Dest", adapter="agent-skills", local=str(local), visibility=visibility
    )


def test_an_approved_passing_candidate_publishes_and_learn_releases_it(tmp_path: Path, trove: Path) -> None:
    cand = make(tmp_path)
    assert candidates.check(cand).ok
    candidates.review(cand, approve=True, reviewer="lead", reason="cases cover the flake patterns")
    src = dest_source(tmp_path)
    out = candidates.publish(cand, src)
    assert (
        (out / "SKILL.md").is_file()
        and not (out / "review.json").exists()
        and not (out / "evaluation.json").exists()
    )
    first = Source(
        id=src.id,
        title="Dest",
        adapter="agent-skills",
        local=src.local,
        first_party=True,
        default_license="MIT",
    )
    result = learn.Learner(trove).learn(first, Path(str(src.local)), None, {first.id: 0})
    learn.finalize(trove, [result], [first])
    assert [i["name"] for i in catalog.load(trove)] == ["fix-flaky-tests"]
    assert (
        releases.history(releases.load(trove), f"skill:{first.id}/fix-flaky-tests")[0]["version"] == "1.0.0"
    )


@pytest.mark.parametrize(
    ("cases", "expected"),
    [
        (
            [
                {"id": "pos-1", "kind": "positive", "passed": True},
                {"id": "reg-1", "kind": "regression", "passed": False},
            ],
            "cases failed: reg-1",
        ),
        ([{"id": "pos-1", "kind": "positive", "passed": True}], "one positive and one regression"),
    ],
)
def test_a_failed_or_thin_evaluation_cannot_publish(tmp_path: Path, cases: list[dict], expected: str) -> None:
    cand = make(tmp_path, cases=cases)
    candidates.review(cand, approve=True, reviewer="lead", reason="looks fine")
    with pytest.raises(candidates.CandidateError, match=expected):
        candidates.publish(cand, dest_source(tmp_path))
    assert not any(dest_source(tmp_path).local and Path(str(dest_source(tmp_path).local)).iterdir())


def test_rejected_unreviewed_and_re_evaluated_candidates_cannot_publish(tmp_path: Path) -> None:
    cand = make(tmp_path)
    with pytest.raises(candidates.CandidateError, match="not reviewed"):
        candidates.publish(cand, dest_source(tmp_path))
    candidates.review(cand, approve=False, reviewer="lead", reason="too project-specific")
    with pytest.raises(candidates.CandidateError, match="review rejected: too project-specific"):
        candidates.publish(cand, dest_source(tmp_path))
    candidates.review(cand, approve=True, reviewer="lead", reason="generalised now")
    later = time.time() + 5
    os.utime(cand / "evaluation.json", (later, later))
    with pytest.raises(candidates.CandidateError, match="changed after the review"):
        candidates.publish(cand, dest_source(tmp_path))


def test_internal_lessons_never_reach_a_public_source(tmp_path: Path) -> None:
    cand = make(tmp_path)
    candidates.review(cand, approve=True, reviewer="lead", reason="ok")
    with pytest.raises(candidates.CandidateError, match="internal-only candidate cannot go to public source"):
        candidates.publish(cand, dest_source(tmp_path, "public"), visibility="internal")
    assert (
        candidates.publish(cand, dest_source(tmp_path, "internal"), visibility="internal") / "SKILL.md"
    ).is_file()


def test_licence_and_secret_gates(tmp_path: Path) -> None:
    gpl = make(tmp_path, "gpl-thing", license_text=GPL)
    assert any("not allowed" in f for f in candidates.check(gpl).failed)
    leaky = make(tmp_path, "leaky-thing", extra={"cfg.env": "AWS_KEY=" + "AKIA" + "ABCDEFGHIJKLMNOP" + "\n"})
    assert any("secret-shaped" in f for f in candidates.check(leaky).failed)
    with pytest.raises(candidates.CandidateError, match="visibility"):
        candidates.check(gpl, visibility="secret")
