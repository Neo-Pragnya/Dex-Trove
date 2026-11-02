from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dex_trove import learn
from dex_trove.cli import app
from dex_trove.sources import Source

from .test_candidates import make

runner = CliRunner()


@pytest.fixture
def checkout(
    trove: Path, source: Source, upstream: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """A learned trove inside a Dex-Trove-shaped checkout, used as the working directory."""
    result = learn.Learner(trove).learn(source, upstream, "abc", {source.id: 0})
    learn.finalize(trove, [result], [source])
    root = trove.parent
    (root / "sources.yaml").write_text(
        f"sources:\n  - id: dest\n    title: Dest\n    adapter: agent-skills\n    local: {tmp_path / 'dest'}\n"
    )
    (tmp_path / "dest").mkdir()
    (root / "src" / "dex_trove").mkdir(parents=True)
    monkeypatch.chdir(root)
    return root


def ok(*args: str) -> str:
    res = runner.invoke(app, list(args))
    assert res.exit_code == 0, res.output
    return res.output


def test_lock_verify_and_install_locked(checkout: Path, tmp_path: Path) -> None:
    out = ok("lock", "alpha", "plugin:up/kit", "--lock-file", "dex.lock.json")
    assert "skill:up/alpha@1.0.0" in out and "agent:up/helper" in out  # the plugin pinned its members
    assert "pin(s) valid" in ok("verify-lock", "--lock-file", "dex.lock.json", "--fetch")
    out = ok(
        "install",
        "--locked",
        "--lock-file",
        "dex.lock.json",
        "--target",
        "dir",
        "--path",
        str(tmp_path / "out"),
    )
    assert (tmp_path / "out/skills/up.alpha/SKILL.md").is_file(), out
    bad = runner.invoke(
        app, ["install", "alpha", "--locked", "--target", "dir", "--path", str(tmp_path / "o")]
    )
    assert bad.exit_code == 2 and "don't name items too" in bad.output
    assert runner.invoke(app, ["install", "--target", "dir", "--path", str(tmp_path / "o")]).exit_code == 2
    assert runner.invoke(app, ["lock", "alpha@9.9.9"]).exit_code == 2
    Path("broken.json").write_text("{}")
    assert runner.invoke(app, ["verify-lock", "--lock-file", "broken.json"]).exit_code == 2


def test_release_commands(checkout: Path) -> None:
    assert "1.0.0" in ok("release", "list", "alpha")
    assert json.loads(ok("release", "list", "alpha", "--json"))["key"] == "skill:up/alpha"
    assert "yanked" in ok("release", "yank", "alpha@1.0.0", "--reason", "broken")
    assert "yanked: broken" in ok("release", "list", "alpha")
    assert runner.invoke(app, ["release", "yank", "alpha", "--reason", "x"]).exit_code == 2
    ok("release", "unyank", "alpha@1.0.0")
    assert "→ skill:up/runner" in ok(
        "release", "deprecate", "alpha", "--reason", "old", "--replaced-by", "runner"
    )
    assert "no forks recorded" in ok("release", "lineage", "alpha")
    assert json.loads(ok("release", "lineage", "alpha", "--json"))["children"] == []
    assert "change(s) recorded" in ok("release", "record")
    assert runner.invoke(app, ["release", "list", "nothing-here"]).exit_code == 2


def test_related_command(checkout: Path) -> None:
    ok("release", "deprecate", "alpha", "--reason", "old", "--replaced-by", "runner")
    ok("release", "record")
    assert "replaced-by" in ok("related", "alpha")
    data = json.loads(ok("related", "alpha", "--json", "--type", "replaced-by"))
    assert [r["target"] for r in data["relations"]] == ["skill:up/runner"]
    assert "no relations of type requires" in ok("related", "alpha", "--type", "requires")


def test_candidate_commands(checkout: Path, tmp_path: Path) -> None:
    cand = make(tmp_path)
    assert json.loads(ok("candidate", "check", str(cand), "--json"))["ok"] is True
    failing = runner.invoke(app, ["candidate", "publish", str(cand), "--to", "dest"])
    assert failing.exit_code == 1 and "not reviewed" in failing.output
    ok("candidate", "review", str(cand), "--approve", "--reviewer", "lead", "--reason", "good")
    assert "published to" in ok("candidate", "publish", str(cand), "--to", "dest")
    assert (tmp_path / "dest/fix-flaky-tests/SKILL.md").is_file()
    assert runner.invoke(app, ["candidate", "publish", str(cand), "--to", "nope"]).exit_code == 2
    assert runner.invoke(app, ["candidate", "check", str(cand), "--visibility", "secret"]).exit_code == 2
    assert (
        runner.invoke(app, ["candidate", "review", str(cand), "--reviewer", " ", "--reason", "x"]).exit_code
        == 2
    )


def test_ledger_commands_refuse_outside_a_checkout(
    trove: Path, source: Source, upstream: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = learn.Learner(trove).learn(source, upstream, "abc", {source.id: 0})
    learn.finalize(trove, [result], [source])
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    res = runner.invoke(app, ["release", "yank", "alpha@1.0.0", "--reason", "x"])
    assert res.exit_code == 2 and "inside a Dex-Trove checkout" in res.output


def test_validate_since_catches_an_edited_release(checkout: Path) -> None:
    import subprocess

    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@e",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@e",
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
    }
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "x"]):
        subprocess.run(["git", *args], cwd=checkout, env=env, check=True, capture_output=True)
    ledger_path = checkout / "trove" / "releases.json"
    data = json.loads(ledger_path.read_text())
    data["items"]["skill:up/alpha"]["releases"][0]["released_at"] = "1999-01-01T00:00:00+00:00"
    ledger_path.write_text(json.dumps(data))
    res = runner.invoke(app, ["validate", "--since", "HEAD"])
    assert res.exit_code == 1 and "releases are immutable" in res.output


def test_ananke_handoff_pins_exactly_and_runs_nothing(checkout: Path) -> None:
    import tomllib

    ok("lock", "alpha", "agent:up/helper", "instruction:up/py")
    res = runner.invoke(app, ["ananke", "handoff"])
    assert res.exit_code == 0, res.output
    toml_text = res.stdout.split("note:")[0]
    data = tomllib.loads(toml_text)["tool"]["ananke"]
    assert data["skills"] == {"up/alpha": "1.0.0"}
    assert data["agent"] == [{"name": "up/helper", "version": "1.0.0"}]
    assert "has no project requirement for instructions" in " ".join(res.output.split())
    assert not Path("pyproject.toml").exists()
