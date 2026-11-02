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


def test_install_exits_non_zero_when_nothing_was_installed(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A refused hook (no --allow-exec) installs nothing; scripts must see a failure, not exit 0."""
    from typer.testing import CliRunner

    from dex_trove import catalog
    from dex_trove.cli import app

    hooks = [i for i in catalog.load() if i["kind"] == "hook"]
    if not hooks:
        import pytest

        pytest.skip("no hook in this trove")
    monkeypatch.chdir(tmp_path)
    ref = f"{hooks[0]['namespace']}/{hooks[0]['name']}"
    result = CliRunner().invoke(app, ["install", ref, "--target", "dir", "--path", "vendor"])
    assert result.exit_code == 1, result.output
    assert not (tmp_path / "vendor" / "hooks").exists()


# ---------------------------------------------------------------------------------- Claude Code compatibility
COPILOT_AGENT = """---
description: 'Reviews pull requests'
name: 'PR Reviewer'
model: GPT-4.1
tools: ['codebase', 'edit/editFiles', 'runCommands', 'vscodeAPI', 'github/*']
---

# PR Reviewer

Body text stays byte-for-byte: `tools: [x]` in prose is not frontmatter.
"""


def test_copilot_agent_is_adapted_for_claude() -> None:
    from dex_trove.claude_compat import MARKER, adapt_agent

    text, notes = adapt_agent(COPILOT_AGENT)
    head, body = text.split("\n---\n", 1)
    assert MARKER in head
    assert "tools: Read, Grep, Glob, Edit, Write, Bash" in head  # only Claude tool names
    assert "model:" not in head and "name: PR Reviewer" in head
    assert body == COPILOT_AGENT.split("\n---\n", 1)[1]  # body untouched
    assert any("vscodeAPI" in n and "github/*" in n for n in notes)
    assert any("GPT-4.1" in n for n in notes)


def test_unmappable_tools_fall_back_to_read_only_never_to_everything() -> None:
    from dex_trove.claude_compat import adapt_agent

    text, notes = adapt_agent("---\nname: x\ndescription: d\ntools: ['vscodeAPI', 'problems']\n---\nbody\n")
    assert "tools: Read, Grep, Glob" in text
    assert any("read-only" in n for n in notes)


def test_claude_models_are_kept_or_normalised() -> None:
    from dex_trove.claude_compat import map_model

    assert map_model("sonnet") == "sonnet" and map_model("claude-opus-5-5") == "claude-opus-5-5"
    assert map_model("Claude Sonnet 4.5") == "sonnet"
    assert map_model("GPT-5") is None and map_model("gpt-4o") is None


def test_plain_agent_installs_unchanged(trove: Path, source: Source, upstream: Path, tmp_path: Path) -> None:
    _learned(trove, source, upstream)
    claude = tmp_path / "claude"
    install(["agent:up/helper"], target="claude", path=claude)
    assert (claude / "agents/helper.md").read_bytes() == (upstream / "agents/Helper.agent.md").read_bytes()


def test_install_never_replaces_what_dex_did_not_write(
    trove: Path, source: Source, upstream: Path, tmp_path: Path
) -> None:
    _learned(trove, source, upstream)
    claude = tmp_path / "claude"
    mine = claude / "skills" / "alpha"
    mine.mkdir(parents=True)
    (mine / "SKILL.md").write_text("my own skill\n")
    [res] = install(["alpha"], target="claude", path=claude)
    assert res.dest is None and "wasn't installed by Dex" in res.skipped
    assert (mine / "SKILL.md").read_text() == "my own skill\n"
    [res] = install(["alpha"], target="claude", path=claude, force=True)
    assert res.dest == mine and "my own skill" not in (mine / "SKILL.md").read_text()


def test_reinstall_replaces_only_its_own_unedited_copy(
    trove: Path, source: Source, upstream: Path, tmp_path: Path
) -> None:
    _learned(trove, source, upstream)
    claude = tmp_path / "claude"
    install(["alpha"], target="claude", path=claude)
    assert (claude / ".dex-trove-installed.json").is_file()
    [res] = install(["alpha"], target="claude", path=claude)  # unedited: replaced quietly
    assert res.dest is not None
    (claude / "skills/alpha/SKILL.md").write_text("edited by me\n")
    [res] = install(["alpha"], target="claude", path=claude)
    assert res.dest is None and (claude / "skills/alpha/SKILL.md").read_text() == "edited by me\n"


def test_identical_copy_from_an_older_dex_is_adopted(
    trove: Path, source: Source, upstream: Path, tmp_path: Path
) -> None:
    import shutil

    from dex_trove import catalog

    _learned(trove, source, upstream)
    claude = tmp_path / "claude"
    item = catalog.resolve(catalog.load(), "alpha")
    shutil.copytree(
        catalog.item_path(item), claude / "skills/alpha", ignore=shutil.ignore_patterns("*.json", "*.yaml")
    )
    [res] = install(["alpha"], target="claude", path=claude)  # no manifest yet, same bytes: Dex's own copy
    assert res.dest is not None


def test_a_symlinked_skill_is_never_followed(
    trove: Path, source: Source, upstream: Path, tmp_path: Path
) -> None:
    _learned(trove, source, upstream)
    claude = tmp_path / "claude"
    real = tmp_path / "my-skills" / "alpha"
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("linked skill\n")
    (claude / "skills").mkdir(parents=True)
    (claude / "skills" / "alpha").symlink_to(real)
    [res] = install(["alpha"], target="claude", path=claude)
    assert res.dest is None and "symlink" in res.skipped
    install(["alpha"], target="claude", path=claude, force=True)
    assert (real / "SKILL.md").read_text() == "linked skill\n"  # the link was replaced, its target kept
    assert not (claude / "skills" / "alpha").is_symlink()
