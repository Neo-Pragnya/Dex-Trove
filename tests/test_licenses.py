from __future__ import annotations

from pathlib import Path

import pytest
from conftest import MIT, OFL, PROPRIETARY

from dex_trove import licenses

APACHE = (Path(licenses.__file__).parent / "license_texts" / "Apache-2.0.txt").read_text()


@pytest.mark.parametrize(
    ("text", "spdx", "verdict"),
    [
        (MIT, "MIT", "allow"),
        (APACHE, "Apache-2.0", "allow"),
        (PROPRIETARY, "LicenseRef-Proprietary", "deny"),
        (OFL, "OFL-1.1", "allow"),
        ("GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007", "GPL-3.0-only", "deny"),
        ("Attribution-NonCommercial 4.0 International", "CC-BY-NC-4.0", "deny"),
        ("Attribution-ShareAlike 4.0 International", "CC-BY-SA-4.0", "review"),
        ("Copyright Foo. All rights reserved.", "LicenseRef-Proprietary", "deny"),
        ("Do whatever, I guess", None, "deny"),
    ],
)
def test_classify_text(text: str, spdx: str | None, verdict: str) -> None:
    got, _ = licenses.classify_text(text)
    assert got == spdx
    assert licenses.verdict_for(got) == verdict


def test_deny_marker_beats_allow_fingerprint() -> None:
    spdx, _ = licenses.classify_text(MIT + "\nusers may not redistribute this file")
    assert spdx == "LicenseRef-Proprietary"


@pytest.mark.parametrize(
    ("expr", "verdict"),
    [
        ("MIT", "allow"),
        ("MIT OR GPL-3.0-only", "allow"),
        ("MIT AND GPL-3.0-only", "deny"),
        ("(Apache-2.0 OR MIT)", "allow"),
        ("Apache-2.0 WITH LLVM-exception", "allow"),
        ("MPL-2.0", "review"),
    ],
)
def test_expressions(expr: str, verdict: str) -> None:
    assert licenses.evaluate_expression(expr)[1] == verdict


def test_frontmatter_values() -> None:
    assert licenses.classify_frontmatter("Complete terms in LICENSE.txt") is None
    assert licenses.classify_frontmatter("Proprietary. LICENSE.txt has complete terms").verdict == "deny"
    assert licenses.classify_frontmatter("Apache 2.0").spdx == "Apache-2.0"
    assert licenses.classify_frontmatter(None) is None


def test_copyright_lines_skip_licence_prose() -> None:
    assert licenses.copyright_lines(APACHE) == ""
    assert licenses.copyright_lines(MIT) == "Copyright (c) 2026 Upstream Authors"


def test_nested_licence_names_are_strict() -> None:
    assert licenses.NESTED_LICENSE_RE.search("ArsenalSC-OFL.txt")
    assert licenses.NESTED_LICENSE_RE.search("LICENSE.md")
    assert not licenses.NESTED_LICENSE_RE.search("pdftk-server-license.md")
