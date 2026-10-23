"""Ananke bridge, docs export, notices, sources and the learn CLI end to end."""

from __future__ import annotations

import json
import stat
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dex_trove import ananke_bridge, learn, notices, sources
from dex_trove.cli import app
from dex_trove.docs_export import export, rewrite_relative
from dex_trove.sources import Source


def _learned(trove: Path, source: Source, upstream: Path) -> None:
    result = learn.Learner(trove).learn(source, upstream, "abc123", {source.id: 0})
    learn.finalize(trove, [result], [source])


# --------------------------------------------------------------------------- ananke bridge
@pytest.fixture
def fake_ananke(tmp_path: Path) -> tuple[Path, Path]:
    """An `ananke` stand-in that records its argv and the item dirs it was offered."""
    log = tmp_path / "ananke.log"
    exe = tmp_path / "ananke"
    exe.write_text(f'#!/bin/sh\necho "$@" >> "{log}"\nls "$3"/*/ >> "{log}" 2>/dev/null\necho "registered"\n')
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return exe, log


def test_ananke_sync_filters_and_skips_flagged(
    trove: Path, source: Source, upstream: Path, tmp_path: Path, fake_ananke: tuple[Path, Path]
) -> None:
    _learned(trove, source, upstream)
    # Troves learned before 0.1.5 kept placeholder items with `secret_flags`; the bridge must still skip them.
    cat_path = trove / "catalog.json"
    cat = json.loads(cat_path.read_text())
    for item in cat["items"]:
        if item["name"] == "fonts":
            item["secret_flags"] = ["generic-credential SKILL.md:9"]
    cat_path.write_text(json.dumps(cat))
    exe, log = fake_ananke
    selected, proc = ananke_bridge.sync(project=tmp_path, kinds=["skill"], ananke_bin=str(exe))
    names = {i["name"] for i in selected}
    assert "alpha" in names and "fonts" not in names  # flagged placeholder item skipped
    assert proc.returncode == 0
    text = log.read_text()
    assert "registry learn" in text and f"--project {tmp_path}" in text
    assert "up.alpha" in text and "up.fonts" not in text

    selected, _ = ananke_bridge.sync(
        project=tmp_path, names=["fonts"], include_flagged=True, ananke_bin=str(exe), dry_run=True
    )
    assert [i["name"] for i in selected] == ["fonts"]
    assert "--dry-run" in log.read_text()


def test_ananke_sync_errors(
    trove: Path, source: Source, upstream: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _learned(trove, source, upstream)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    monkeypatch.setattr(ananke_bridge.sys, "executable", str(tmp_path / "no-venv" / "python"))
    with pytest.raises(ananke_bridge.AnankeError, match="not found"):
        ananke_bridge.sync(project=tmp_path, kinds=["skill"])
    venv_bin = tmp_path / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "ananke").write_text("#!/bin/sh\n")
    monkeypatch.setattr(ananke_bridge.sys, "executable", str(venv_bin / "python"))
    assert ananke_bridge.find_ananke() == str(venv_bin / "ananke")  # unactivated venv
    with pytest.raises(ananke_bridge.AnankeError, match="no trove items"):
        ananke_bridge.sync(project=tmp_path, kinds=["skill"], sources=["nope"], ananke_bin="/bin/echo")


# --------------------------------------------------------------------------- docs export
def test_rewrite_relative_targets() -> None:
    item = {
        "entry": "SKILL.md",
        "dir": "skills/a.napkin",
        "source": {"repo": "https://github.com/o/r", "commit": "c0ffee", "path": "skills/napkin"},
    }
    out = rewrite_relative(
        "![s](../../skills/napkin/a.svg) [r](refs/x.md#top) [e](https://x.y) [h](#h) <img src='i.png'>", item
    )
    assert "https://raw.githubusercontent.com/o/r/c0ffee/skills/napkin/a.svg" in out
    assert "https://github.com/o/r/blob/c0ffee/skills/napkin/refs/x.md#top" in out
    assert "(https://x.y)" in out and "(#h)" in out
    assert "(https://github.com/o/r/blob/c0ffee/spec)" in rewrite_relative("[s](/spec/)", item)
    assert "src='https://raw.githubusercontent.com/o/r/c0ffee/skills/napkin/i.png'" in out

    first_party = {
        "entry": "SKILL.md",
        "dir": "skills/n.x",
        "source": {"repo": None, "commit": None, "path": "x"},
    }
    assert "Dex-Trove/main/trove/skills/n.x/a.png" in rewrite_relative("![a](a.png)", first_party)


def test_docs_export_writes_pages_and_indexes(
    trove: Path, source: Source, upstream: Path, tmp_path: Path
) -> None:
    _learned(trove, source, upstream)
    out = tmp_path / "site"
    n = export(trove, out, [source], [])
    pages = sorted(p.name for p in (out / "content" / "items").glob("*.md"))
    assert n == len(pages) and "skill--up.alpha.md" in pages
    page = (out / "content" / "items" / "skill--up.alpha.md").read_text()
    assert page.startswith("---\n") and "kind: skill" in page and "# alpha" not in page  # H1 dropped
    search = json.loads((out / "data" / "search.json").read_text())
    assert {"id", "kind", "ns", "name", "title", "d", "tags", "lic"} <= set(search[0])
    meta = json.loads((out / "data" / "trove.json").read_text())
    assert meta["total"] == n and meta["sources"][0]["id"] == "up"
    agent = (out / "content" / "items" / "agent--up.helper.md").read_text()
    assert "upstream_meta:" in agent and "hook_events: []" in agent
    assert "part_of:\n- plugin:up/kit" in agent


# --------------------------------------------------------------------------- notices
def test_notices_aggregate_licences(trove: Path, source: Source, upstream: Path) -> None:
    _learned(trove, source, upstream)
    text = notices.render(trove, [source])
    assert text.startswith("# Third-party notices")
    assert "## Upstream" in text and "MIT (" in text and "Apache-2.0 (" in text
    assert "Copyright (c) 2026 Upstream Authors" in text
    assert "## Licence texts" in text and "Permission is hereby granted" in text


# --------------------------------------------------------------------------- sources
def test_sources_load_and_fetch_local(tmp_path: Path, upstream: Path) -> None:
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        f"""
sources:
  - id: up
    title: Up
    adapter: awesome-copilot
    local: {upstream}
    license: {{ first_party: true, default: MIT }}
    exclude: ["skills/alpha/*.tmp"]
    items: {{ alpha: {{ inspired_by: [{{ title: X, url: "https://x" }}] }} }}
candidates:
  - {{ repo: a/b, license: MIT, decision: later, offers: things }}
"""
    )
    srcs, cands = sources.load(cfg)
    assert srcs[0].first_party and srcs[0].default_license == "MIT" and srcs[0].items["alpha"]
    assert cands[0].repo == "a/b"
    root, commit = sources.fetch(srcs[0])
    assert root == upstream and commit is None
    with pytest.raises(FileNotFoundError):
        sources.fetch(Source(id="x", title="x", adapter="agent-skills", local=str(tmp_path / "missing")))


def test_sources_fetch_git_clone(tmp_path: Path, upstream: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for args in (
        ["init", "-q"],
        ["add", "-A"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"],
    ):
        subprocess.run(["git", *args], cwd=upstream, check=True)
    monkeypatch.setenv("DEX_TROVE_CACHE", str(tmp_path / "cache"))
    src = Source(id="g", title="g", adapter="awesome-copilot", repo=upstream.as_uri())
    root, commit = sources.fetch(src)
    assert (root / "skills" / "alpha" / "SKILL.md").is_file() and commit and len(commit) == 40
    root2, commit2 = sources.fetch(src)  # second call refreshes in place
    assert root2 == root and commit2 == commit
    assert src.upstream_url(commit, "x", True) == f"{upstream.as_uri()}"


# --------------------------------------------------------------------------- CLI learn/validate/notices
def test_cli_learn_in_a_checkout(tmp_path: Path, upstream: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "dex_trove").mkdir(parents=True)
    (repo / "sources.yaml").write_text(
        f"sources:\n  - id: up\n    title: Up\n    adapter: awesome-copilot\n    local: {upstream}\n"
    )
    monkeypatch.chdir(repo)
    monkeypatch.delenv("DEX_TROVE_ROOT", raising=False)
    runner = CliRunner()
    res = runner.invoke(app, ["learn", "--dry-run"])
    assert res.exit_code == 0 and "admitted" in res.output and not (repo / "trove").exists()
    res = runner.invoke(app, ["learn"])
    assert res.exit_code == 0, res.output
    assert (repo / "trove" / "catalog.json").is_file() and (repo / "THIRD_PARTY_NOTICES.md").is_file()
    assert runner.invoke(app, ["validate"]).exit_code == 0
    assert runner.invoke(app, ["learn", "nope"]).exit_code == 2
    assert runner.invoke(app, ["notices"]).exit_code == 0
    assert runner.invoke(app, ["catalog"]).exit_code == 0
    out = runner.invoke(app, ["sources"])
    assert out.exit_code == 0 and "up" in out.output
    res = runner.invoke(app, ["docs", "export", "--out", str(tmp_path / "web")])
    assert res.exit_code == 0 and (tmp_path / "web" / "data" / "search.json").is_file()
    assert runner.invoke(app, ["list", "--kind", "skill"]).exit_code == 0
    assert runner.invoke(app, ["license", str(upstream)]).exit_code == 0
    (repo / "THIRD_PARTY_NOTICES.md").write_text("stale")
    assert runner.invoke(app, ["validate"]).exit_code == 1
