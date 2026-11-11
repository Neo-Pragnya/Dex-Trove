"""CAP-scaffold-harvesting-04: a reviewed template becomes a skill candidate with provenance, through the gates."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dex_trove import candidates, templates
from dex_trove.cli import app
from dex_trove.sources import Source

from .conftest import MIT

GPL = "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n"
DESCRIPTION = "A FastAPI service scaffold with tests and a Dockerfile. Use it to start a small HTTP API."


def template(tmp: Path, *, license_text: str | None = MIT, extra: dict[str, str] | None = None) -> Path:
    root = tmp / "fastapi-service"
    (root / "src" / "{{ cookiecutter.package }}").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "{{ cookiecutter.package }}"\nversion = "0.1.0"\n'
    )
    (root / "src" / "{{ cookiecutter.package }}" / "app.py").write_text('TITLE = "__SERVICE_NAME__"\n')
    (root / "tests" / "test_app.py").write_text("def test_title():\n    assert True\n")
    if license_text:
        (root / "LICENSE").write_text(license_text)
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "x.js").write_text("module.exports = 1\n")
    for rel, text in (extra or {}).items():
        (root / rel).write_text(text)
    return root


def wrap(tmp: Path, src: Path, out: str = "cand", **kw) -> Path:
    args = {"name": "fastapi-service", "description": DESCRIPTION, "version": "1.2.0", **kw}
    return templates.from_template(src, tmp / out, **args)


def test_a_template_becomes_a_pinned_versioned_candidate(tmp_path: Path) -> None:
    cand = wrap(tmp_path, template(tmp_path))
    prov = json.loads((cand / "provenance.json").read_text())
    assert prov["version"] == "1.2.0" and prov["license"] == "MIT"
    assert set(prov["files"]) == {
        "LICENSE",
        "pyproject.toml",
        "src/{{ cookiecutter.package }}/app.py",
        "tests/test_app.py",
    }  # no .git, no node_modules
    assert prov["placeholders"] == ["SERVICE_NAME", "package"]
    assert (cand / "template" / "tests" / "test_app.py").is_file()
    skill = (cand / "SKILL.md").read_text()
    assert "license: MIT" in skill and "`SERVICE_NAME`" in skill and prov["tree_digest"] in skill


def test_the_same_template_gives_the_same_digest(tmp_path: Path) -> None:
    src = template(tmp_path)
    a = json.loads((wrap(tmp_path, src, "a") / "provenance.json").read_text())
    time.sleep(1.1)
    b = json.loads((wrap(tmp_path, src, "b") / "provenance.json").read_text())
    assert a["tree_digest"] == b["tree_digest"] and a["files"] == b["files"]
    assert {k: v for k, v in a.items() if k != "wrapped_at"} == {
        k: v for k, v in b.items() if k != "wrapped_at"
    }
    (src / "pyproject.toml").write_text("changed\n")
    c = json.loads((wrap(tmp_path, src, "c") / "provenance.json").read_text())
    assert c["tree_digest"] != a["tree_digest"]


def test_nothing_is_published_until_its_checks_pass_and_a_reviewer_approves(tmp_path: Path) -> None:
    cand = wrap(tmp_path, template(tmp_path))
    evaluation = json.loads((cand / "evaluation.json").read_text())
    ids = {c["id"]: c["kind"] for c in evaluation["cases"]}
    assert ids == {"builds": "positive", "tests-pass": "regression"}
    report = candidates.check(cand)
    assert not report.ok and any("evaluation cases failed" in f for f in report.failed)
    for case in evaluation["cases"]:
        case["passed"] = True
    evaluation["finished_at"] = "2026-11-10T00:00:00+00:00"
    (cand / "evaluation.json").write_text(json.dumps(evaluation))
    assert candidates.check(cand).ok
    dest = tmp_path / "dest"
    dest.mkdir()
    source = Source(id="dest", title="Dest", adapter="agent-skills", local=str(dest), visibility="public")
    with pytest.raises(candidates.CandidateError):
        candidates.publish(cand, source)  # not reviewed yet
    candidates.review(cand, approve=True, reviewer="lead", reason="scaffold builds and its tests pass")
    out = candidates.publish(cand, source)
    assert (out / "provenance.json").is_file() and (out / "template" / "pyproject.toml").is_file()
    assert not (out / "evaluation.json").exists()


def test_credentials_licences_and_bad_input_are_refused_with_what_to_fix(tmp_path: Path) -> None:
    leaky = template(
        tmp_path / "leaky", extra={".env.example": "AWS_KEY=" + "AKIA" + "ABCDEFGHIJKLMNOP" + "\n"}
    )
    with pytest.raises(candidates.CandidateError, match="secret-shaped"):
        wrap(tmp_path, leaky, "x1")
    assert not (tmp_path / "x1").exists()  # nothing written
    with pytest.raises(candidates.CandidateError, match="no licence"):
        wrap(tmp_path, template(tmp_path / "nolic", license_text=None), "x2")
    assert wrap(
        tmp_path, template(tmp_path / "flag", license_text=None), "x3", license_id="Apache-2.0"
    ).is_dir()
    with pytest.raises(candidates.CandidateError, match="isn't allowed"):
        wrap(tmp_path, template(tmp_path / "gpl", license_text=GPL), "x4")
    with pytest.raises(candidates.CandidateError, match="no such template"):
        wrap(tmp_path, tmp_path / "missing", "x5")
    with pytest.raises(candidates.CandidateError, match="MAJOR.MINOR.PATCH"):
        wrap(tmp_path, template(tmp_path / "v"), "x6", version="v1")
    with pytest.raises(candidates.CandidateError, match="lowercase"):
        wrap(tmp_path, template(tmp_path / "n"), "x7", name="Bad Name")
    empty = tmp_path / "empty"
    (empty / ".git").mkdir(parents=True)
    with pytest.raises(candidates.CandidateError, match="nothing to wrap"):
        wrap(tmp_path, empty, "x8")
    wrap(tmp_path, template(tmp_path / "twice"), "x9")
    with pytest.raises(candidates.CandidateError, match="already exists"):
        wrap(tmp_path, template(tmp_path / "twice2"), "x9")


def test_cli(tmp_path: Path) -> None:
    src = template(tmp_path)
    runner = CliRunner()
    out = tmp_path / "c"
    res = runner.invoke(
        app,
        [
            "candidate",
            "from-template",
            str(src),
            "--name",
            "fastapi-service",
            "--description",
            DESCRIPTION,
            "--version",
            "2.0.0",
            "--out",
            str(out),
            "--json",
        ],
    )
    assert res.exit_code == 0, res.output
    data = json.loads(res.stdout)
    assert data["version"] == "2.0.0" and data["files"] == 4 and data["tree_digest"].startswith("sha256:")
    res = runner.invoke(
        app,
        ["candidate", "from-template", str(tmp_path / "nope"), "--name", "x-y", "--description", DESCRIPTION],
    )
    assert res.exit_code == 2
