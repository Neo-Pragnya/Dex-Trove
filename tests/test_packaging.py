"""The published metadata tells scanners the truth about what the wheel contains."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_license_expression_covers_every_bundled_licence() -> None:
    expression = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["license"]
    declared = set(re.split(r"\s+(?:AND|OR)\s+", expression))
    items = json.loads((ROOT / "trove" / "catalog.json").read_text())["items"]
    bundled = {i["license"]["spdx"] for i in items} | {
        c for i in items for c in i["license"].get("components", [])
    }
    # A licence policy (Black Duck, Xray, ...) compares this expression with what it finds in the files;
    # declaring only MIT while shipping Apache-2.0 and OFL-1.1 content reads as a licence conflict.
    assert bundled <= declared, f"add {sorted(bundled - declared)} to [project] license in pyproject.toml"


def test_trove_ships_no_secret_shaped_items() -> None:
    items = json.loads((ROOT / "trove" / "catalog.json").read_text())["items"]
    assert not [i["id"] for i in items if i.get("secret_flags")]


def test_curation_only_names_items_in_the_trove() -> None:
    from dex_trove import catalog, facets

    facets.build(catalog.load(ROOT / "trove"))  # raises on a curated id that no longer exists


def test_facets_sidecar_is_current_and_covers_every_item() -> None:
    from dex_trove import catalog, facets

    items = catalog.load(ROOT / "trove")
    on_disk = json.loads((ROOT / "trove" / "facets.json").read_text())
    assert on_disk == facets.build(items, check_stale=False), "run `dex facets build`"
    assert on_disk["count"] == len(items)


def test_taxonomy_reference_page_is_current() -> None:
    from dex_trove import facets

    page = (ROOT / "docs" / "reference" / "taxonomy.md").read_text()
    assert page == facets.taxonomy_markdown(records=facets.load(ROOT / "trove")), "run `dex facets doc`"


def test_reuse_matrix_is_current() -> None:
    from dex_trove import reuse

    page = (ROOT / "docs" / "reference" / "reuse-matrix.md").read_text()
    assert page == reuse.markdown(ROOT / "trove"), "run `dex docs reuse`"


def test_feedback_is_moderated_through_github_forms_only() -> None:
    """Curation and feedback need a GitHub identity and evidence; the site itself takes no comments or stars."""
    forms = ROOT / ".github" / "ISSUE_TEMPLATE"
    curation = yaml.safe_load((forms / "curation.yml").read_text())
    required = {b["id"] for b in curation["body"] if b.get("validations", {}).get("required")}
    assert {"item", "change", "proposal", "evidence"} <= required
    feedback = yaml.safe_load((forms / "item-feedback.yml").read_text())
    assert {"item", "problem", "details"} <= {
        b["id"] for b in feedback["body"] if b.get("validations", {}).get("required")
    }
    assert "Code of Conduct" in feedback["body"][0]["attributes"]["value"]
    pages = "".join(p.read_text() for p in (ROOT / "website" / "src" / "pages").rglob("*.astro"))
    assert not any(x in pages for x in ("<textarea", "giscus", 'localStorage.setItem("star'))
