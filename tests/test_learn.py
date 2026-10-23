from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from dex_trove import catalog, learn
from dex_trove.sources import Source


def run(trove: Path, source: Source, upstream: Path, commit: str = "abc123") -> learn.SourceResult:
    result = learn.Learner(trove).learn(source, upstream, commit, {source.id: 0})
    learn.finalize(trove, [result], [source])
    return result


def by_id(trove: Path) -> dict[str, dict]:
    return {f"{i['kind']}:{i['name']}": i for i in catalog.load(trove)}


def test_admission_rules(trove: Path, source: Source, upstream: Path) -> None:
    result = run(trove, source, upstream)
    items = by_id(trove)
    reasons = {e.name: e.reason for e in result.excluded}

    assert reasons["closed"] == "license-denied"
    assert reasons["leaky"] == "secret"
    assert reasons["teaching"] == "secret-shaped"  # a placeholder still gets a wheel quarantined
    assert reasons["canvas"] == "out-of-scope"
    assert {"skill:alpha", "skill:apache-declared", "skill:see-file", "skill:fonts", "skill:runner"} <= set(
        items
    )
    assert items["skill:see-file"]["license"]["spdx"] == "MIT"
    assert items["skill:fonts"]["license"]["components"] == ["OFL-1.1"]
    assert items["skill:runner"]["executes_code"] is True
    assert "skill:teaching" not in items
    excluded = (trove / "EXCLUDED.json").read_text()
    assert "generic-credential SKILL.md" in excluded and "abc123xyz789" not in excluded  # where, never what
    assert items["instruction:py"]["apply_to"] == "**/*.py"
    assert (
        items["agent:helper"]["source"]["url"]
        == "https://github.com/example/up/blob/abc123/agents/Helper.agent.md"
    )


def test_licence_text_travels_with_item(trove: Path, source: Source, upstream: Path) -> None:
    run(trove, source, upstream)
    alpha = trove / "skills" / "up.alpha"
    assert "Permission is hereby granted" in (alpha / "LICENSE.upstream").read_text()
    declared = trove / "skills" / "up.apache-declared" / "LICENSE.upstream"
    assert "Apache License" in declared.read_text()  # canonical text when upstream only declares it


def test_upstream_bytes_unmodified(trove: Path, source: Source, upstream: Path) -> None:
    run(trove, source, upstream)
    assert (trove / "skills/up.alpha/SKILL.md").read_bytes() == (
        upstream / "skills/alpha/SKILL.md"
    ).read_bytes()


def test_plugin_becomes_bundle_without_excluded_members(trove: Path, source: Source, upstream: Path) -> None:
    run(trove, source, upstream)
    kit = by_id(trove)["plugin:kit"]
    assert kit["version"] == "2.1.0"
    assert kit["members"] == ["skill:up/alpha", "agent:up/helper"]
    manifest = yaml.safe_load((trove / kit["dir"] / "ananke.yaml").read_text())
    assert manifest["kind"] == "bundle"
    assert [m["ref"] for m in manifest["members"]] == ["ananke://skill/up/alpha", "ananke://agent/up/helper"]


def test_versions_bump_only_on_change_and_removals(trove: Path, source: Source, upstream: Path) -> None:
    run(trove, source, upstream)
    assert by_id(trove)["skill:alpha"]["version"] == "1.0.0"
    run(trove, source, upstream)
    assert by_id(trove)["skill:alpha"]["version"] == "1.0.0"
    (upstream / "skills/alpha/SKILL.md").write_text("---\nname: alpha\ndescription: 'changed'\n---\nNew.\n")
    result = run(trove, source, upstream)
    assert by_id(trove)["skill:alpha"]["version"] == "1.0.1"
    import shutil

    shutil.rmtree(upstream / "skills" / "runner")
    result = run(trove, source, upstream)
    assert "skill:up/runner" in result.removed
    assert not (trove / "skills" / "up.runner").exists()


def test_duplicates_prefer_higher_priority_source(
    trove: Path, source: Source, upstream: Path, tmp_path: Path
) -> None:
    run(trove, source, upstream)
    mirror = tmp_path / "mirror"
    (mirror / "skills").mkdir(parents=True)
    (mirror / "LICENSE").write_text((upstream / "LICENSE").read_text())
    import shutil

    shutil.copytree(upstream / "skills" / "alpha", mirror / "skills" / "alpha")
    second = Source(
        id="mirror", title="Mirror", adapter="agent-skills", priority=1, options={"roots": ["skills"]}
    )
    result = learn.Learner(trove).learn(second, mirror, None, {"up": 0, "mirror": 1})
    assert [e.reason for e in result.excluded] == ["duplicate"]


def test_manifests_are_valid_for_ananke(trove: Path, source: Source, upstream: Path) -> None:
    models = pytest.importorskip("ananke.plexus.registry.models")
    run(trove, source, upstream)
    for item in catalog.load(trove):
        manifest = yaml.safe_load((trove / item["dir"] / "ananke.yaml").read_text())
        models.ArtifactManifest.model_validate(manifest)


def test_validate_detects_drift(trove: Path, source: Source, upstream: Path) -> None:
    from dex_trove.validate import validate

    run(trove, source, upstream)
    assert validate(trove) == []
    (trove / "skills/up.alpha/SKILL.md").write_text("tampered")
    assert any("drifted" in p for p in validate(trove))


def test_slugify() -> None:
    assert learn.slugify("CSharpExpert") == "csharp-expert"
    assert learn.slugify("microsoft_learn_contributor") == "microsoft-learn-contributor"
    assert learn.slugify("  Weird Name!! ") == "weird-name"
    assert json.dumps(learn.slugify("x" * 100)).count("x") == 64


def test_dexignore_hides_items_without_trace(
    trove: Path, source: Source, upstream: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (upstream / ".dexignore").write_text("# private\nalpha\nagents/Helper*\n")
    user_cfg = tmp_path / "user-ignore"
    user_cfg.write_text("up:runner\nother-source:fonts\n")
    monkeypatch.setenv("DEX_TROVE_IGNORE", str(user_cfg))
    result = run(trove, source, upstream)
    items = by_id(trove)
    assert result.ignored == 3  # alpha + helper (source file) + runner (user file, scoped to "up")
    assert "skill:alpha" not in items and "agent:helper" not in items and "skill:runner" not in items
    assert "skill:fonts" in items  # scoped to another source → not ignored here
    recorded = (trove / "EXCLUDED.json").read_text() + (trove / "trove.lock.json").read_text()
    assert "alpha" not in recorded and "runner" not in recorded
    # kit's remaining member (alpha) is ignored and closed is denied → no admissible members → out-of-scope
    assert "plugin:kit" not in items


def test_ignore_patterns_unit(tmp_path: Path) -> None:
    from dex_trove import ignore

    assert ignore.is_ignored(["Chosen"], "skills/some-dir", ["some-*"])
    assert ignore.is_ignored(["x"], "skills/x", ["skills/*"])
    assert not ignore.is_ignored(["x"], "skills/x", [])


def test_duplicates_are_caught_within_a_single_run(
    trove: Path, source: Source, upstream: Path, tmp_path: Path
) -> None:
    """The first learn on a fresh trove must already refuse a duplicate (not only the second one)."""
    import shutil

    mirror = tmp_path / "mirror"
    (mirror / "skills").mkdir(parents=True)
    (mirror / "LICENSE").write_text((upstream / "LICENSE").read_text())
    shutil.copytree(upstream / "skills" / "alpha", mirror / "skills" / "alpha")
    second = Source(
        id="mirror", title="Mirror", adapter="agent-skills", priority=1, options={"roots": ["skills"]}
    )
    learner = learn.Learner(trove)  # one run, both sources, nothing in the catalog yet
    priority = {"up": 0, "mirror": 1}
    first = learner.learn(source, upstream, "abc123", priority)
    result = learner.learn(second, mirror, None, priority)
    assert first.items
    assert [e.reason for e in result.excluded] == ["duplicate"]


def test_relearning_unchanged_upstream_keeps_lock_byte_identical(
    trove: Path, source: Source, upstream: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import itertools

    tick = itertools.count(1)  # every call is a later instant, as if each run took a while
    monkeypatch.setattr(learn, "now_iso", lambda: f"2026-01-01T00:00:{next(tick):02d}Z")
    run(trove, source, upstream)
    before = (trove / "trove.lock.json").read_text()
    run(trove, source, upstream)
    assert (trove / "trove.lock.json").read_text() == before
    run(trove, source, upstream, commit="def456")  # a new upstream commit is a real change
    old, new = json.loads(before), json.loads((trove / "trove.lock.json").read_text())
    assert new["sources"][source.id]["learned_at"] > old["sources"][source.id]["learned_at"]


def test_same_name_in_two_kinds_keeps_each_version_history(
    trove: Path, source: Source, upstream: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (upstream / "agents" / "Alpha.agent.md").write_text(
        "---\nname: alpha\ndescription: 'An agent.'\n---\n\nHi.\n"
    )
    run(trove, source, upstream)
    first = {(i["kind"], i["name"]): i for i in catalog.load(trove)}
    assert ("agent", "alpha") in first and ("skill", "alpha") in first
    monkeypatch.setattr(learn, "now_iso", lambda: "2099-01-01T00:00:00Z")
    run(trove, source, upstream)
    again = {(i["kind"], i["name"]): i for i in catalog.load(trove)}
    for key in (("agent", "alpha"), ("skill", "alpha")):
        assert again[key]["learned_at"] == first[key]["learned_at"]  # unchanged content keeps its record
