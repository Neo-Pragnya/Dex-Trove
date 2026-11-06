"""A component bundled inside an item keeps its licence notice, whatever happens to the item's folder."""

from __future__ import annotations

import tomllib
from pathlib import Path

from dex_trove import notices, sources

ROOT = Path(__file__).resolve().parents[1]


def test_every_bundled_component_is_in_the_notices_with_its_full_text() -> None:
    srcs, _ = sources.load(ROOT / "sources.yaml")
    text = notices.render(ROOT / "trove", srcs)
    manifest = tomllib.loads((ROOT / "notices" / "bundled.toml").read_text())
    for c in manifest["component"]:
        assert f"### {c['name']} ({c['licence']})" in text
        assert (ROOT / c["text"]).read_text().strip() in text
        assert (ROOT / c["path"]).is_file(), f"{c['path']} is listed but no longer shipped"


def test_the_committed_notices_are_current() -> None:
    srcs, _ = sources.load(ROOT / "sources.yaml")
    assert (ROOT / "THIRD_PARTY_NOTICES.md").read_text() == notices.render(ROOT / "trove", srcs)
