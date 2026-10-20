"""Licence identification and the redistribution policy (DESIGN.md §5).

Licences are classified from their *text* where possible. Filenames and repo badges are not trusted, because
repos routinely redistribute material under terms that differ from their own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ALLOW = frozenset(
    {
        "MIT",
        "MIT-0",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "0BSD",
        "Unlicense",
        "CC0-1.0",
        "CC-BY-4.0",
        "Zlib",
        "BSL-1.0",
        "Python-2.0",
        "PSF-2.0",
        "OFL-1.1",  # fonts bundled with software (anthropic canvas-design)
    }
)
REVIEW_PREFIXES = ("MPL-", "EPL-", "LGPL-", "CC-BY-SA-")
DENY_PREFIXES = ("GPL-", "AGPL-", "CC-BY-NC", "CC-BY-ND", "SSPL", "BUSL", "LicenseRef-", "NOASSERTION")

ALLOW_V, REVIEW_V, DENY_V = "allow", "review", "deny"

_ALIASES = {
    "mit": "MIT",
    "mit license": "MIT",
    "the mit license": "MIT",
    "mit-0": "MIT-0",
    "apache-2.0": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "apache-2": "Apache-2.0",
    "apache 2": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "apache software license": "Apache-2.0",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "bsd 3-clause": "BSD-3-Clause",
    "isc": "ISC",
    "0bsd": "0BSD",
    "unlicense": "Unlicense",
    "the unlicense": "Unlicense",
    "cc0-1.0": "CC0-1.0",
    "cc0": "CC0-1.0",
    "cc-by-4.0": "CC-BY-4.0",
    "cc by 4.0": "CC-BY-4.0",
    "cc-by-sa-4.0": "CC-BY-SA-4.0",
    "zlib": "Zlib",
    "bsl-1.0": "BSL-1.0",
    "mpl-2.0": "MPL-2.0",
    "gpl-2.0": "GPL-2.0-only",
    "gpl-3.0": "GPL-3.0-only",
    "agpl-3.0": "AGPL-3.0-only",
    "lgpl-3.0": "LGPL-3.0-only",
}
_SPDX_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]*$")
LICENSE_FILE_RE = re.compile(r"^(licen[cs]e|copying|unlicense)([._-].*)?$", re.IGNORECASE)
# Licence files *inside* an item (bundled fonts, vendored code). Strict names only: a doc that merely
# talks about a licence (e.g. references/pdftk-server-license.md) is content, not terms.
NESTED_LICENSE_RE = re.compile(r"^(licen[cs]e|copying)([._-].*)?$|(^|[-_.])ofl\.txt$", re.IGNORECASE)

# Phrases that mean "you may not redistribute this", whatever else the text says.
_DENY_MARKERS = (
    "governed by your agreement with",
    "users may not",
    "you may not distribute",
    "may not be redistributed",
    "distribute, sublicense, or transfer these materials",
    "does not convey or imply any license",
    "proprietary and confidential",
    "unauthorized copying of this file",
)


@dataclass(frozen=True)
class Classification:
    spdx: str | None
    verdict: str
    evidence: str
    notice: str = ""  # copyright lines worth preserving in THIRD_PARTY_NOTICES


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("’", "'")).strip()


def normalise_id(value: str) -> str | None:
    """Map a free-text licence label or SPDX id to a canonical SPDX id (or ``None``)."""
    raw = value.strip().strip("'\"").strip()
    if not raw:
        return None
    alias = _ALIASES.get(raw.lower())
    if alias:
        return alias
    if _SPDX_TOKEN.match(raw):
        for known in (*ALLOW, "MPL-2.0", "CC-BY-SA-4.0", "GPL-3.0-only", "AGPL-3.0-only"):
            if raw.lower() == known.lower():
                return known
        return raw  # unknown-but-well-formed id; policy decides
    return None


def verdict_for(spdx: str | None) -> str:
    if not spdx:
        return DENY_V
    if spdx in ALLOW:
        return ALLOW_V
    if spdx.startswith(REVIEW_PREFIXES):
        return REVIEW_V
    return DENY_V


def evaluate_expression(expr: str) -> tuple[str | None, str]:
    """Evaluate a simple SPDX expression. ``OR`` passes if any branch is allowed, ``AND`` needs all."""
    text = expr.strip().strip("()")
    rank = {ALLOW_V: 0, REVIEW_V: 1, DENY_V: 2}
    if re.search(r"\s+OR\s+", text):
        parts = [evaluate_expression(p) for p in re.split(r"\s+OR\s+", text)]
        best = min(parts, key=lambda p: rank[p[1]])
        return best if best[0] else (None, DENY_V)
    if re.search(r"\s+AND\s+", text):
        parts = [evaluate_expression(p) for p in re.split(r"\s+AND\s+", text)]
        worst = max(parts, key=lambda p: rank[p[1]])
        if worst[1] != ALLOW_V:
            return worst
        return " AND ".join(p[0] or "?" for p in parts), ALLOW_V
    base = re.split(r"\s+WITH\s+", text)[0]
    spdx = normalise_id(base)
    return spdx, verdict_for(spdx)


def classify_text(text: str) -> tuple[str | None, str]:
    """Identify a licence from its full text. Returns ``(spdx, reason)``; spdx ``None`` = unknown."""
    t = _norm(text)
    for marker in _DENY_MARKERS:
        if marker in t:
            return "LicenseRef-Proprietary", f"restrictive terms ({marker!r})"
    if "gnu affero general public license" in t:
        return "AGPL-3.0-only", "AGPL text"
    if "gnu lesser general public license" in t:
        return "LGPL-3.0-only", "LGPL text"
    if "gnu general public license" in t:
        return ("GPL-2.0-only" if "version 2" in t and "version 3" not in t else "GPL-3.0-only"), "GPL text"
    if "business source license" in t:
        return "BUSL-1.1", "BUSL text"
    if "server side public license" in t:
        return "SSPL-1.0", "SSPL text"
    if "sil open font license" in t:
        return "OFL-1.1", "SIL OFL text"
    if "mozilla public license" in t:
        return "MPL-2.0", "MPL text"
    if "apache license" in t and "version 2.0" in t:
        return "Apache-2.0", "Apache-2.0 text"
    if "permission is hereby granted, free of charge" in t:
        if "the above copyright notice and this permission notice shall be included" in t:
            return "MIT", "MIT text"
        return "MIT-0", "MIT-0 text"
    if "redistribution and use in source and binary forms" in t:
        return ("BSD-3-Clause" if "neither the name" in t else "BSD-2-Clause"), "BSD text"
    if "permission to use, copy, modify, and/or distribute this software for any purpose" in t:
        return ("ISC" if "the above copyright notice" in t else "0BSD"), "ISC-family text"
    if "free and unencumbered software released into the public domain" in t:
        return "Unlicense", "Unlicense text"
    if "cc0 1.0 universal" in t or "creative commons legal code cc0" in t:
        return "CC0-1.0", "CC0 text"
    if "attribution-noncommercial" in t:
        return "CC-BY-NC-4.0", "CC BY-NC text"
    if "attribution-noderivatives" in t or "attribution-noderivs" in t:
        return "CC-BY-ND-4.0", "CC BY-ND text"
    if "attribution-sharealike 4.0" in t:
        return "CC-BY-SA-4.0", "CC BY-SA text"
    if "attribution 4.0 international" in t:
        return "CC-BY-4.0", "CC BY text"
    if "boost software license" in t:
        return "BSL-1.0", "Boost text"
    if "altered source versions must be plainly marked" in t:
        return "Zlib", "zlib text"
    if "all rights reserved" in t:
        return "LicenseRef-Proprietary", "'all rights reserved' with no recognised grant"
    return None, "unrecognised licence text"


_COPYRIGHT = re.compile(r"^\s*(?:copyright\b|©)", re.IGNORECASE)
_NOT_A_NOTICE = ("license", "notice", "owner", "holder", "statement", "permission", "the above", "[")


def copyright_lines(text: str, limit: int = 3) -> str:
    """Actual copyright statements (``Copyright 2025 Foo``), not licence prose that mentions copyright."""
    lines = [
        ln.strip()
        for ln in text.splitlines()
        if _COPYRIGHT.match(ln) and not any(b in ln.lower() for b in _NOT_A_NOTICE)
    ]
    return "\n".join(dict.fromkeys(lines[:limit]))


def classify_file(path: Path, label: str | None = None) -> Classification:
    text = path.read_text(encoding="utf-8", errors="replace")
    spdx, reason = classify_text(text)
    return Classification(
        spdx=spdx,
        verdict=verdict_for(spdx),
        evidence=f"{label or path.name}: {reason}",
        notice=copyright_lines(text),
    )


def license_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.iterdir() if p.is_file() and not p.is_symlink() and LICENSE_FILE_RE.match(p.name)
    )


def classify_frontmatter(value: object) -> Classification | None:
    """Interpret a ``license:`` frontmatter value. ``None`` means 'look at files instead'."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    lower = text.lower()
    if "proprietary" in lower:
        return Classification("LicenseRef-Proprietary", DENY_V, f"frontmatter license: {text!r}")
    spdx, verdict = evaluate_expression(text)
    if spdx is None:
        return None  # e.g. "Complete terms in LICENSE.txt" → defer to the file
    return Classification(spdx, verdict, f"frontmatter license: {text!r}")
