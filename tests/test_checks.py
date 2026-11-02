from __future__ import annotations

from pathlib import Path

from dex_trove import checks, learn
from dex_trove.sources import Source


def test_install_checks_verify_what_each_tool_needs(trove: Path, source: Source, upstream: Path) -> None:
    (upstream / "skills" / "wordy").mkdir()
    (upstream / "skills/wordy/SKILL.md").write_text(
        "---\nname: wordy\ndescription: '" + "x" * 1100 + "'\n---\nBody.\n"
    )
    (upstream / "instructions" / "loose.instructions.md").write_text(
        "---\ndescription: 'no glob'\n---\nRules.\n"
    )
    result = learn.Learner(trove).learn(source, upstream, "abc", {source.id: 0})
    learn.finalize(trove, [result], [source])  # learn runs the checks too
    data = checks.load(trove)
    items = data["items"]
    assert data["generator"].startswith("dex-trove ")
    assert items["skill:up/alpha"] == {"claude": "pass", "copilot": "pass"}
    assert items["instruction:up/py"] == {"copilot": "pass"}  # no Claude layout: not checked, not failed
    assert "longer than 1024" in items["skill:up/wordy"]["claude"]
    assert "no applyTo glob" in items["instruction:up/loose"]["copilot"]
    assert items["agent:up/helper"]["claude"] == "pass"
    assert data["summary"]["claude"]["fail"] >= 1
