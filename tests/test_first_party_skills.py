"""Acceptance checks for the first-party capability skills, run from the trove copy (what users install).

Each test maps to the spec's acceptance scenarios (Capability-Specifications, workstreams 02 and 06).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "trove" / "skills"


def run(script: str, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SKILLS / script), *args], cwd=cwd, capture_output=True, text=True
    )


def test_idea_developer_traces_decisions_and_never_hands_off_unapproved(tmp_path: Path) -> None:
    s = "neo-pragnya.idea-developer/scripts/session.py"
    assert run(s, "init", "--title", "Expenses", "--domain", "web-app", cwd=tmp_path).returncode == 0
    for qid, text in [
        ("goal-1", "File expenses by phone"),
        ("users-1", "Staff, managers"),
        ("outcomes-1", "90% filed by phone"),
        ("scope-1", "No card feeds"),
    ]:
        assert run(s, "answer", qid, text, cwd=tmp_path).returncode == 0
    uncited = run(s, "decide", "Use a native app", "--from", "web-1", cwd=tmp_path)
    assert uncited.returncode == 2 and "must cite" in uncited.stderr  # all choices trace to answers
    assert run(s, "decide", "Mobile web", "--from", "goal-1", cwd=tmp_path).returncode == 0
    blocked = run(s, "handoff", cwd=tmp_path)
    assert (
        blocked.returncode == 2 and "unapproved decisions D1" in blocked.stderr
    )  # nothing silently approved
    first = run(s, "prd", cwd=tmp_path).stdout
    assert "proposed, not approved" in first and "## Actors" in first and "## Out of scope" in first
    assert run(s, "approve", "D1", "--by", "PO", cwd=tmp_path).returncode == 0
    assert run(s, "prd", cwd=tmp_path).stdout == run(s, "prd", cwd=tmp_path).stdout  # deterministic
    handoff = run(s, "handoff", cwd=tmp_path)
    assert handoff.returncode == 0 and handoff.stdout.startswith("ananke spec create --title Expenses")
    assert "Mobile web" in (tmp_path / "idea-session.json").read_text()  # resumable state on disk
    assert (
        run(
            s,
            "next",
            cwd=tmp_path,
        ).returncode
        == 0
    )
    assert run(s, "init", "--title", "x", "--domain", "nope", cwd=tmp_path / "..").returncode == 2


def test_tech_selection_refuses_popularity_and_unowned_licence_breaks(tmp_path: Path) -> None:
    ref = SKILLS / "neo-pragnya.tech-selection" / "references"
    shutil.copy(ref / "architecture.md", tmp_path)
    req = json.loads((ref / "request.example.json").read_text())
    s = "neo-pragnya.tech-selection/scripts/decide.py"

    def check(r: dict) -> subprocess.CompletedProcess[str]:
        (tmp_path / "r.json").write_text(json.dumps(r))
        return run(s, "check", "r.json", cwd=tmp_path)

    ok = check(req)
    assert (
        ok.returncode == 0 and "LGPL-3.0 is not in the allowed list" in ok.stdout
    )  # mismatched licence flagged
    popular = json.loads(json.dumps(req))
    popular["options"][0]["evidence"] = [
        e for e in popular["options"][0]["evidence"] if e["kind"] == "popularity"
    ]
    assert "popularity alone" in check(popular).stderr
    lgpl = dict(req, chosen="Dramatiq + RabbitMQ")
    assert "add an exception for 'licence'" in check(lgpl).stderr
    lgpl["exceptions"] = [{"policy": "licence", "reason": "dynamic linking only"}]
    assert "has no owner" in check(lgpl).stderr  # exceptions require an owner
    broken = json.loads(json.dumps(req))
    broken["enterprise_docs"][0]["cite"] = "architecture.md#nowhere"
    assert "no heading #nowhere" in check(broken).stderr  # citations must resolve
    rec = run(s, "record", "r.json", cwd=tmp_path)
    assert rec.returncode == 1  # the last request written is the broken one: no record
    (tmp_path / "r.json").write_text(json.dumps(req))
    assert run(s, "record", "r.json", cwd=tmp_path).stdout == run(s, "record", "r.json", cwd=tmp_path).stdout


def test_research_questionnaire_offline_partial_honest_and_mergeable(tmp_path: Path) -> None:
    s = "neo-pragnya.research-questionnaire/scripts/questionnaire.py"
    tpl = str(SKILLS / "neo-pragnya.research-questionnaire" / "templates" / "web-app.json")
    assert run(s, "form", tpl, "-o", "f.html", cwd=tmp_path).returncode == 0
    page = (tmp_path / "f.html").read_text()
    assert "connect-src 'none'" in page and "localStorage" not in page  # offline; no hidden storage
    a1 = {
        "schema": "research-questionnaire/answers@1",
        "template": "web-app-discovery",
        "exported_at": "t1",
        "answers": {"problem": "Slow claims", "volume": 250},
    }
    a2 = dict(a1, exported_at="t2", answers={"problem": "Slow claims", "volume": 300})
    (tmp_path / "a1.json").write_text(json.dumps(a1))
    (tmp_path / "a2.json").write_text(json.dumps(a2))
    assert (
        "2 of 9 answered; valid" in run(s, "check", "a1.json", "--template", tpl, cwd=tmp_path).stdout
    )  # partial ok
    assert run(s, "merge", "a1.json", "a2.json", "-o", "m.json", cwd=tmp_path).returncode == 0
    merged = json.loads((tmp_path / "m.json").read_text())
    assert merged["answers"] == {"problem": "Slow claims", "volume": 300}
    assert (
        len(merged["provenance"]["problem"]) == 1 and len(merged["provenance"]["volume"]) == 2
    )  # no duplicates
    prd = json.loads(run(s, "prd", "m.json", "--template", tpl, cwd=tmp_path).stdout)
    assert "signin" in prd["unresolved"] and "signin" not in json.dumps(prd["sections"])  # nothing fabricated
    md = run(s, "markdown", "m.json", "--template", tpl, cwd=tmp_path).stdout
    assert md.startswith("---\n") and "## Open questions" in md
    assert run(s, "check", "missing.json", "--template", tpl, cwd=tmp_path).returncode == 2


def test_scaffold_harvesting_safe_versioned_and_tested(tmp_path: Path) -> None:
    s = "neo-pragnya.scaffold-harvesting/scripts/harvest.py"
    repo = tmp_path / "acme-api"
    (repo / "src" / "acme_api").mkdir(parents=True)
    (repo / "LICENSE").write_text(
        "MIT License\n\nPermission is hereby granted, free of charge, to any person\n"
    )
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "acme-api"\n[tool.pytest]\npackages = ["acme_api"]\n'
    )
    (repo / "src" / "acme_api" / "app.py").write_text("SECRET_BUSINESS_LOGIC = 1\n")
    (repo / ".env").write_text("X=1\n")
    out = run(
        s,
        "template",
        str(repo),
        "-o",
        "tpl",
        "--name",
        "acme-api",
        "--test",
        "grep -q billing_api pyproject.toml",
        cwd=tmp_path,
    )
    assert out.returncode == 0, out.stderr
    files = json.loads((tmp_path / "tpl" / "template.json").read_text())
    assert (
        files["version"] == "1.0.0" and "src/acme_api/app.py" not in files["files"]
    )  # versioned; no app code
    assert "acme" not in (tmp_path / "tpl" / "files" / "pyproject.toml").read_text()
    assert (
        run(s, "test", "tpl", "--set", "project_name=billing-api", cwd=tmp_path).returncode == 0
    )  # installs/tests
    # assembled at runtime so the shipped sdist holds no secret-shaped string
    (repo / "pyproject.toml").write_text("pass" + 'word = "' + "q7" * 6 + '"\n')
    leaky = run(s, "template", str(repo), "-o", "tpl2", "--name", "acme-api", cwd=tmp_path)
    assert leaky.returncode == 2 and not (tmp_path / "tpl2").exists()  # no included credentials
    (repo / "LICENSE").write_text("All rights reserved.\n")
    assert (
        "only permissively licensed"
        in run(s, "template", str(repo), "-o", "tpl3", "--name", "x", cwd=tmp_path).stderr
    )
    assert (
        "publish"
        not in (SKILLS / "neo-pragnya.scaffold-harvesting/scripts/harvest.py")
        .read_text()
        .split("def main")[1]
    )
