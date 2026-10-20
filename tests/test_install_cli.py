from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from dex_trove import learn
from dex_trove.cli import app
from dex_trove.install import install
from dex_trove.sources import Source


def _learned(trove: Path, source: Source, upstream: Path) -> None:
    result = learn.Learner(trove).learn(source, upstream, "abc", {source.id: 0})
    learn.finalize(trove, [result], [source])


def test_install_claude_and_copilot(trove: Path, source: Source, upstream: Path, tmp_path: Path) -> None:
    _learned(trove, source, upstream)
    claude = tmp_path / "claude"
    done = install(["alpha", "agent:up/helper"], target="claude", path=claude)
    assert (claude / "skills/alpha/SKILL.md").is_file()
    assert not (claude / "skills/alpha/dex.json").exists()
    assert (claude / "agents/helper.md").is_file()
    assert (claude / "agents/helper.md.LICENSE").is_file()
    assert all(d.dest for d in done)

    gh = tmp_path / "gh"
    done = install(["py", "kit"], target="copilot", path=gh)
    assert (gh / "instructions/py.instructions.md").is_file()
    assert (gh / "skills/alpha/SKILL.md").is_file() and (gh / "agents/helper.agent.md").is_file()


def test_install_unsupported_kind_is_reported(
    trove: Path, source: Source, upstream: Path, tmp_path: Path
) -> None:
    _learned(trove, source, upstream)
    [res] = install(["py"], target="claude", path=tmp_path / "c")
    assert res.dest is None and "no native claude layout" in res.skipped


def test_cli_search_show(trove: Path, source: Source, upstream: Path) -> None:
    _learned(trove, source, upstream)
    runner = CliRunner()
    assert "dex-trove" in runner.invoke(app, ["--version"]).output
    out = runner.invoke(app, ["search", "alpha", "--json"]).output
    assert "up/alpha" in out
    out = runner.invoke(app, ["show", "up/fonts"]).output
    assert "MIT" in out and "Upstream" in out
    assert runner.invoke(app, ["show", "nope"]).exit_code == 2
