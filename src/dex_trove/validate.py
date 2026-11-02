"""``dex validate``: the CI gate over a trove (DESIGN.md §8)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from dex_trove import catalog
from dex_trove.learn import _NAME_RE, KIND_TO_ANANKE, rebuild_catalog
from dex_trove.licenses import ALLOW_V


def validate(trove: Path, *, notices_text: str | None = None, notices_file: Path | None = None) -> list[str]:
    problems: list[str] = []
    try:
        from ananke.plexus.registry.models import ArtifactManifest  # optional, strongest check
    except Exception:  # noqa: BLE001 - ananke is optional
        ArtifactManifest = None  # noqa: N806
    listed = catalog.load(trove)
    on_disk = rebuild_catalog(trove)
    if [i["id"] + i["kind"] for i in listed] != [i["id"] + i["kind"] for i in on_disk]:
        problems.append("catalog.json is stale — run `dex learn` or `dex catalog`")
    for it in on_disk:
        d = trove / it["dir"]
        where = f"{it['kind']}:{it['id']}"
        if not _NAME_RE.match(it["name"]):
            problems.append(f"{where}: invalid name")
        if it["license"]["verdict"] != ALLOW_V:
            problems.append(f"{where}: licence verdict {it['license']['verdict']}")
        for rel in it["files"]:
            if not (d / rel).is_file():
                problems.append(f"{where}: missing file {rel}")
        hashes = {
            rel: hashlib.sha256((d / rel).read_bytes()).hexdigest()
            for rel in it["files"]
            if (d / rel).is_file()
        }
        if hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest() != it["content_hash"]:
            problems.append(f"{where}: content drifted from upstream copy (hash mismatch)")
        manifest_path = d / "ananke.yaml"
        if not manifest_path.is_file():
            problems.append(f"{where}: missing ananke.yaml")
            continue
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("kind") != KIND_TO_ANANKE[it["kind"]] or manifest.get("version") != it["version"]:
            problems.append(f"{where}: ananke.yaml disagrees with dex.json")
        if ArtifactManifest is not None:
            try:
                ArtifactManifest.model_validate(manifest)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{where}: ananke manifest invalid: {str(exc).splitlines()[0]}")
    if (
        notices_text is not None
        and notices_file is not None
        and (not notices_file.is_file() or notices_file.read_text(encoding="utf-8") != notices_text)
    ):
        problems.append("THIRD_PARTY_NOTICES.md is stale — run `dex notices`")
    problems += _facet_problems(trove, listed)
    return problems


def _facet_problems(trove: Path, items: list[dict[str, Any]]) -> list[str]:
    """facets.json must exist, match a rebuild, and use only known taxonomy terms."""
    from dex_trove import facets, taxonomy

    path = trove / facets.FACETS_FILE
    if not path.is_file():
        return ["facets.json is missing — run `dex facets build`"]
    try:
        expected = facets.build(items, check_stale=False)
    except taxonomy.TaxonomyError as exc:
        return [f"taxonomy or curation invalid: {exc}"]
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    if on_disk != expected:
        return ["facets.json is stale — run `dex facets build`"]
    return []
