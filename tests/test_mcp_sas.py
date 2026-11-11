"""SAS server: inventory, lineage verdicts, the pandas draft (run for real when pandas is reachable) and parity."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from dex_trove.mcp import sas
from dex_trove.mcp.common import Context, ToolError
from dex_trove.mcp.server import Server

FIXTURE = Path(__file__).parent / "fixtures/sas"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    shutil.copytree(FIXTURE, tmp_path / "sas")
    return tmp_path


def make(root: Path) -> Server:
    return Server("sas", sas.INSTRUCTIONS, list(sas.TOOLS), Context(root=root, server="sas"))


def test_inventory(root: Path) -> None:
    out = make(root).call("sas_inventory", {"paths": ["sas/claims.sas"]})
    steps = {(s["kind"], s["name"], s["line"]): s for s in out["steps"]}
    data = steps[("data", "data", 5)]
    assert data["inputs"] == ["raw.claims"] and data["outputs"] == ["work.claims"]
    assert steps[("proc", "sort", 18)]["outputs"] == ["work.sorted"]
    assert steps[("proc", "means", 22)]["outputs"] == ["work.summary"]
    assert out["lets"] == {"minamt": "100"} and out["libnames"] == {"raw": "/data/raw"}
    assert out["macros"] == {"report": {"file": "sas/claims.sas", "line": 32}}
    assert ("macro-call", "report", 35) in steps


def test_lineage_verdicts(root: Path) -> None:
    out = make(root).call("sas_lineage", {})
    verdicts = {(s["kind"], s["name"]): s["verdict"] for s in out["steps"]}
    assert verdicts[("proc", "sort")] == "supported" and verdicts[("proc", "means")] == "supported"
    assert verdicts[("proc", "freq")] == "partial"
    assert verdicts[("macro-def", "report")] == verdicts[("macro-call", "report")] == "unsupported"
    assert verdicts[("proc", "reg")] == "unsupported"
    running = next(s for s in out["steps"] if s["outputs"] == ["work.running"])
    assert running["verdict"] == "unsupported" and "RETAIN" in running["reasons"][0]
    assert {"from": "raw.claims", "to": "sas/claims.sas:5"} in out["edges"]
    assert out["mermaid"].startswith("flowchart LR")
    assert (root / "dex-evidence/sas/sas-lineage.sarif").is_file()
    assert out["counts"]["unsupported"] == 4


def test_expressions_keep_sas_semantics() -> None:
    assert sas.expr("amount < 100") == 'sas_lt(df["amount"], 100)'
    assert sas.expr("x = . or y ne 'A'") == 'sas_or(sas_eq(df["x"], MISSING), sas_ne(df["y"], \'A\'))'
    assert sas.expr("not (a in (1, 2))") == 'sas_not((sas_in(df["a"], [1, 2])))'
    assert sas.expr("sum(a, b) / 2") == 'sas_div(sas_sum(df["a"], df["b"]), 2)'
    assert sas.expr("'it''s' || name") == 'sas_concat("it\'s", df["name"])'
    for bad in ("put(x, 8.)", "first.id", "a = ("):
        with pytest.raises(sas.Untranslatable):
            sas.expr(bad)


def test_dataset_options_are_not_dropped_silently(tmp_path: Path) -> None:
    (tmp_path / "p.sas").write_text(
        "data b; set a(where=(x > 1)); y = x; run;\ndata c; set a; if x then do; y = 1; end; run;\n"
    )
    out = make(tmp_path).call("sas_lineage", {})
    assert all(s["verdict"] == "unsupported" for s in out["steps"])
    assert "dataset options" in out["steps"][0]["reasons"][0]
    assert any("DO" in r for r in out["steps"][1]["reasons"])


def test_draft_is_valid_python_and_refuses_to_overwrite(root: Path) -> None:
    out = make(root).call("sas_draft", {"output": "py/claims.py"})
    assert out["counts"] == {"supported": 3, "partial": 1, "unsupported": 4}
    source = (root / "py/claims.py").read_text()
    assert "# line 9: else if amount < &minamt then amount_flag = 'S'" in source
    assert 'sas_lt(df["amount"], 100)' in source
    assert "not_translated('sas/claims.sas:38: not translated" in source
    with pytest.raises(ToolError, match="exists"):
        make(root).call("sas_draft", {"output": "py/claims.py"})


def _pandas(spec: str) -> list[str] | None:
    uv = shutil.which("uv")
    if not uv:
        return None
    cmd = [uv, "run", "--no-project", "--with", spec, "python"]
    probe = subprocess.run([*cmd, "-c", "import pandas"], capture_output=True, timeout=300, check=False)
    return cmd if probe.returncode == 0 else None


@pytest.mark.parametrize("spec", ["pandas>=2.2,<3", "pandas>=3"])
def test_draft_runs_and_matches_sas_expectations(root: Path, spec: str) -> None:
    python = _pandas(spec)
    if python is None:
        pytest.skip("pandas isn't reachable through uv here")
    make(root).call("sas_draft", {"output": "py/claims.py"})
    data = root / "in"
    data.mkdir()
    shutil.copy(root / "sas/raw.claims.csv", data / "raw.claims.csv")
    strict = subprocess.run(
        [*python, "py/claims.py", "--data", "in", "--out", "out"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert strict.returncode != 0 and "NotTranslated" in strict.stderr
    done = subprocess.run(
        [*python, "py/claims.py", "--data", "in", "--out", "out", "--skip-unsupported"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stderr.count("skipped:") == 4
    assert not (root / "out/work.running.csv").exists()
    server = make(root)
    plan = "dex-evidence/sas/draft-plan.json"
    for name, keys in (
        ("work.claims", ["id"]),
        ("work.sorted", []),
        ("work.summary", ["region"]),
        ("work.flags", ["amount_flag"]),
    ):
        res = server.call(
            "sas_parity",
            {
                "expected": f"sas/expected.{name}.csv",
                "actual": f"out/{name}.csv",
                "keys": keys,
                "abs_tol": 1e-6,
                "plan": plan,
            },
        )
        assert res["mismatches"] == [] and res["problems"] == [], (name, res)
        assert res["status"] == "incomplete"  # other steps in the program weren't translated


def test_parity_finds_differences(tmp_path: Path) -> None:
    (tmp_path / "e.csv").write_text("k,v,t\n1,1.0,a\n2,2.0,b\n3,.,c\n")
    (tmp_path / "a.csv").write_text("K,V,T,extra\n2,2.0000001,b  \n1,1.5,a,\n4,,d,\n")
    server = Server("sas", sas.INSTRUCTIONS, list(sas.TOOLS), Context(root=tmp_path, server="sas"))
    out = server.call("sas_parity", {"expected": "e.csv", "actual": "a.csv", "keys": ["k"], "abs_tol": 1e-3})
    assert out["status"] == "mismatch"
    assert [(m["column"], m["expected"], m["actual"]) for m in out["mismatches"]] == [("v", "1.0", "1.5")]
    assert any("{'k': '3'}" in p for p in out["problems"]) and any("{'k': '4'}" in p for p in out["problems"])
    assert out["extra_columns"] == ["extra"]
    report = json.loads((tmp_path / "dex-evidence/sas/parity-a.json").read_text())
    assert report["tolerance"] == {"abs": 0.001, "rel": 1e-09}
    with pytest.raises(ToolError, match="aren't in both"):
        server.call("sas_parity", {"expected": "e.csv", "actual": "a.csv", "keys": ["nope"]})
