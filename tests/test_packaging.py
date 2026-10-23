"""The published metadata tells scanners the truth about what the wheel contains."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

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
