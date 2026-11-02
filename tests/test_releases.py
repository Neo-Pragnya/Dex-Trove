from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from dex_trove import catalog, install, learn, releases
from dex_trove.sources import Source


def git(*args: str, cwd: Path) -> str:
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
    }
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env
    ).stdout.strip()


def commit_all(repo: Path, message: str) -> str:
    if not (repo / ".git").is_dir():
        git("init", "-q", cwd=repo)
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", message, cwd=repo)
    return git("rev-parse", "HEAD", cwd=repo)


def run(trove: Path, source: Source, upstream: Path, commit: str = "abc123") -> learn.SourceResult:
    result = learn.Learner(trove).learn(source, upstream, commit, {source.id: 0})
    learn.finalize(trove, [result], [source])
    return result


def change_alpha(upstream: Path, text: str) -> None:
    (upstream / "skills/alpha/SKILL.md").write_text(f"---\nname: alpha\ndescription: '{text}'\n---\n{text}\n")


def test_learn_appends_releases_and_never_rewrites_them(trove: Path, source: Source, upstream: Path) -> None:
    run(trove, source, upstream)
    first = copy.deepcopy(releases.load(trove))
    assert [r["version"] for r in releases.history(first, "skill:up/alpha")] == ["1.0.0"]
    run(trove, source, upstream)  # unchanged upstream: no new release
    assert releases.load(trove) == first
    change_alpha(upstream, "changed once")
    run(trove, source, upstream, commit="def456")
    ledger = releases.load(trove)
    hist = releases.history(ledger, "skill:up/alpha")
    assert [r["version"] for r in hist] == ["1.0.0", "1.0.1"]
    assert hist[1]["source"]["commit"] == "def456" and hist[0]["source"]["commit"] == "abc123"
    assert releases.immutability_problems(first, ledger) == []
    assert releases.problems(ledger, catalog.load(trove)) == []


def test_upstream_reusing_a_version_for_new_bytes_gets_a_fresh_number(
    trove: Path, source: Source, upstream: Path
) -> None:
    run(trove, source, upstream)
    kit = releases.history(releases.load(trove), "plugin:up/kit")
    assert kit[-1]["version"] == "2.1.0"
    plugin = upstream / "plugins/kit/plugin.json"
    data = json.loads(plugin.read_text())
    data["description"] = "A kit, changed without a version bump"
    plugin.write_text(json.dumps(data))
    run(trove, source, upstream)
    versions = [r["version"] for r in releases.history(releases.load(trove), "plugin:up/kit")]
    assert versions == ["2.1.0", "2.1.1"]


def test_v1_and_v2_coexist_through_a_lock(
    trove: Path, source: Source, upstream: Path, tmp_path: Path
) -> None:
    c1 = commit_all(upstream, "v1")
    src = Source(id="up", title="Upstream", adapter="awesome-copilot", repo=str(upstream))
    run(trove, src, upstream, commit=c1)
    ledger = releases.load(trove)
    v1 = releases.lock_entry("skill:up/alpha", releases.resolve(ledger, "skill:up/alpha"))
    lock = tmp_path / "dex.lock.json"
    releases.write_lock(lock, [v1], generator="test")

    change_alpha(upstream, "version two")
    c2 = commit_all(upstream, "v2")
    run(trove, src, upstream, commit=c2)
    ledger = releases.load(trove)
    assert releases.resolve(ledger, "skill:up/alpha")["version"] == "1.0.1"  # a new lock picks v2

    # The old pin still installs v1, fetched from its own commit and verified, while the trove holds v2.
    entries = releases.read_lock(lock)
    assert releases.check_lock(ledger, entries) == ([], [])
    done = install.install_locked(entries, target="dir", path=tmp_path / "out")
    assert done[0].dest is not None, done[0].skipped
    installed = (done[0].dest / "SKILL.md").read_text()
    assert "version two" not in installed and "alpha skill for tests" in installed
    assert "version two" in (trove / "skills/up.alpha/SKILL.md").read_text()


def test_a_tampered_pin_is_refused_and_writes_nothing(
    trove: Path, source: Source, upstream: Path, tmp_path: Path
) -> None:
    c1 = commit_all(upstream, "v1")
    src = Source(id="up", title="Upstream", adapter="awesome-copilot", repo=str(upstream))
    run(trove, src, upstream, commit=c1)
    rel = releases.resolve(releases.load(trove), "skill:up/alpha")
    bad = releases.Locked(
        "skill:up/alpha", rel["version"], "0" * 64, rel["source"], rel["entry"], rel["files"]
    )
    with pytest.raises(releases.ReleaseError, match="don't match the released digest"):
        releases.fetch(bad, tmp_path / "x")
    assert not (tmp_path / "x").exists()
    first_party = releases.Locked(
        "skill:up/alpha",
        "1.0.0",
        rel["content_hash"],
        {"repo": None, "commit": None, "path": "a"},
        "SKILL.md",
        ["SKILL.md"],
    )
    with pytest.raises(releases.ReleaseError, match="no upstream commit"):
        releases.fetch(first_party, tmp_path / "y")


def test_yank_and_deprecate_steer_resolution_but_keep_locks_working(
    trove: Path, source: Source, upstream: Path
) -> None:
    run(trove, source, upstream)
    change_alpha(upstream, "second")
    run(trove, source, upstream)
    ledger = releases.load(trove)
    key = "skill:up/alpha"
    pinned = releases.lock_entry(key, releases.resolve(ledger, key))  # 1.0.1
    releases.yank(ledger, key, "1.0.1", "broke the build", at="2026-11-02T00:00:00+00:00")
    assert releases.resolve(ledger, key)["version"] == "1.0.0"
    errors, warnings = releases.check_lock(ledger, [pinned])
    assert errors == [] and "yanked: broke the build" in warnings[0]
    with pytest.raises(releases.ReleaseError, match="needs a reason"):
        releases.yank(ledger, key, "1.0.0", " ", at="x")
    with pytest.raises(releases.ReleaseError, match="not in the ledger"):
        releases.deprecate(ledger, key, "old", at="x", replaced_by="skill:up/nowhere")
    releases.deprecate(ledger, key, "use beta", at="x", replaced_by="skill:up/apache-declared")
    assert all(
        r["deprecated"]["replaced_by"] == "skill:up/apache-declared" for r in releases.history(ledger, key)
    )
    releases.unyank(ledger, key, "1.0.1")
    assert releases.resolve(ledger, key)["version"] == "1.0.1"


def test_immutability_allows_markers_but_not_edits_or_deletions(
    trove: Path, source: Source, upstream: Path
) -> None:
    run(trove, source, upstream)
    before = releases.load(trove)
    after = copy.deepcopy(before)
    releases.yank(after, "skill:up/alpha", "1.0.0", "reason", at="x")
    assert releases.immutability_problems(before, after) == []
    after["items"]["skill:up/alpha"]["releases"][0]["content_hash"] = "f" * 64
    after["items"]["skill:up/runner"]["releases"].clear()
    found = releases.immutability_problems(before, after)
    assert any("alpha@1.0.0: released metadata changed" in p for p in found)
    assert any("runner@1.0.0: release deleted" in p for p in found)


def test_forks_record_lineage_and_dangling_parents_are_caught(
    trove: Path, source: Source, upstream: Path, tmp_path: Path
) -> None:
    run(trove, source, upstream)
    fork_up = tmp_path / "fork-src"
    (fork_up / "skills" / "alpha-plus").mkdir(parents=True)
    (fork_up / "LICENSE").write_text((upstream / "LICENSE").read_text())
    (fork_up / "skills/alpha-plus/SKILL.md").write_text(
        "---\nname: alpha-plus\ndescription: 'alpha, improved'\n---\nMore.\n"
    )
    fork = Source(
        id="mine",
        title="Mine",
        adapter="awesome-copilot",
        repo="https://github.com/example/mine",
        items={"alpha-plus": {"forked_from": "skill:up/alpha"}},
    )
    learner = learn.Learner(trove)
    result = learner.learn(fork, fork_up, "f00d", {"up": 0, "mine": 1})
    learn.finalize(trove, [result], [source, fork])
    ledger = releases.load(trove)
    child = releases.history(ledger, "skill:mine/alpha-plus")[0]
    assert child["parent"]["key"] == "skill:up/alpha" and child["parent"]["version"] == "1.0.0"
    assert releases.lineage(ledger, "skill:up/alpha")["children"] == ["skill:mine/alpha-plus"]
    assert releases.lineage(ledger, "skill:mine/alpha-plus")["parents"][0]["key"] == "skill:up/alpha"
    del ledger["items"]["skill:up/alpha"]
    assert any(
        "fork parent skill:up/alpha is not in the ledger" in p
        for p in releases.problems(ledger, catalog.load(trove))
    )


def test_removed_items_keep_their_history(trove: Path, source: Source, upstream: Path) -> None:
    import shutil

    run(trove, source, upstream)
    shutil.rmtree(upstream / "skills" / "runner")
    run(trove, source, upstream)
    ledger = releases.load(trove)
    assert ledger["items"]["skill:up/runner"]["removed"] is True
    assert releases.history(ledger, "skill:up/runner")[0]["version"] == "1.0.0"
    assert releases.problems(ledger, catalog.load(trove)) == []
