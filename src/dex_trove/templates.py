"""Wrap a reviewed project template as a skill candidate (``dex candidate from-template``).

A template (a scaffold folder: files, placeholders, maybe its own tests) becomes a skill whose ``SKILL.md`` says how
to use it, with the files under ``template/`` and a ``provenance.json`` that pins every file by sha256. It goes
through the normal candidate gates, so nothing is published by this step:

* the licence must be declared (a LICENSE file in the template, or ``--license``) and allowed;
* secret-shaped text refuses the template outright, before anything is written;
* only regular files are copied: no symlinks, version-control or build folders, environments or caches;
* ``version`` and a tree digest (paths and sha256s, no timestamps) identify the template, so the same template
  always gives the same digest;
* ``evaluation.json`` lists the checks found in the template (its tests, its build) with ``passed: null``. The
  candidate fails ``dex candidate check`` until someone runs them and records the result, and a reviewer approves.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from dex_trove import licenses
from dex_trove.candidates import EVALUATION_FILE, EVALUATION_SCHEMA, CandidateError
from dex_trove.learn import (
    MAX_FILE_BYTES,
    MAX_ITEM_BYTES,
    ananke_secret_flags,
    now_iso,
    scan_secrets,
    slugify,
)

PROVENANCE_SCHEMA = "dex-trove/template-provenance@1"
SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".idea",
        ".vscode",
        ".ananke",
    }
)
SKIP_FILES = frozenset({".DS_Store", "Thumbs.db"})
PLACEHOLDERS = (
    re.compile(r"\{\{\s*cookiecutter\.([A-Za-z_][\w]*)\s*\}\}"),
    re.compile(r"\{\{\s*([A-Za-z_][\w]*)\s*\}\}"),
    re.compile(r"__([A-Z][A-Z0-9_]{2,})__"),
)
VERSION = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def _files(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]) or p.name in SKIP_FILES:
            continue
        if p.is_symlink() or not p.is_file():
            continue
        out[rel.as_posix()] = p
    return out


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(files: dict[str, str]) -> str:
    """sha256 over sorted ``path sha256`` lines: the template's identity, with no timestamps in it."""
    lines = "".join(f"{rel} {digest}\n" for rel, digest in sorted(files.items()))
    return "sha256:" + hashlib.sha256(lines.encode()).hexdigest()


def _placeholders(files: dict[str, Path]) -> list[str]:
    found: set[str] = set()
    for rel, p in files.items():
        for pattern in PLACEHOLDERS:
            found.update(pattern.findall(rel))
        if p.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in PLACEHOLDERS:
            found.update(pattern.findall(text))
    return sorted(found)


def _checks(files: dict[str, Path]) -> list[dict[str, str]]:
    """Checks the template carries: its own tests and build. Evaluation runs them; this only lists them."""
    names = set(files)
    cases: list[dict[str, str]] = []
    if "pyproject.toml" in names or "setup.py" in names:
        cases.append({"id": "builds", "kind": "positive", "command": "python -m build --wheel ."})
    if any(re.search(r"(^|/)(tests?/|test_[^/]+\.py$)", n) for n in names):
        cases.append({"id": "tests-pass", "kind": "regression", "command": "python -m pytest -q"})
    if "package.json" in names:
        cases.append({"id": "npm-test", "kind": "regression", "command": "npm test"})
    if "Makefile" in names:
        cases.append({"id": "make-check", "kind": "positive", "command": "make check"})
    if not any(c["kind"] == "positive" for c in cases):
        cases.append(
            {
                "id": "renders",
                "kind": "positive",
                "command": "copy template/ into an empty folder and fill every placeholder",
            }
        )
    if not any(c["kind"] == "regression" for c in cases):
        cases.append(
            {
                "id": "no-leftovers",
                "kind": "regression",
                "command": "no placeholder is left after filling it in",
            }
        )
    return cases


def from_template(
    template: Path,
    out: Path,
    *,
    name: str,
    description: str,
    version: str,
    license_id: str | None = None,
    source_url: str = "",
) -> Path:
    """Write a candidate folder for ``template`` at ``out``. Raises ``CandidateError`` with what to fix."""
    template = template.expanduser()
    if not template.is_dir():
        raise CandidateError(f"{template}: no such template folder")
    if slugify(name) != name or not name:
        raise CandidateError(f"{name!r}: a candidate name is lowercase words joined by hyphens")
    if len(description.strip()) < 40:
        raise CandidateError("say what the template makes and when to use it (40+ characters)")
    if not VERSION.match(version):
        raise CandidateError(f"{version!r}: a template version is MAJOR.MINOR.PATCH, such as 1.0.0")
    if out.exists():
        raise CandidateError(f"{out} already exists; choose another --out")
    files = _files(template.resolve())
    if not files:
        raise CandidateError(f"{template}: nothing to wrap (only skipped folders or no files)")
    big = [r for r, p in files.items() if p.stat().st_size > MAX_FILE_BYTES]
    if big or sum(p.stat().st_size for p in files.values()) > MAX_ITEM_BYTES:
        raise CandidateError(f"too large for a skill: {', '.join(big[:3]) or 'the total size'}")
    secret = scan_secrets(files)
    flags = ananke_secret_flags(files)
    if secret or flags:
        raise CandidateError(
            f"secret-shaped text in the template ({secret or '; '.join(flags[:3])}); remove it first"
        )
    if license_id:
        lic = licenses.classify_frontmatter(license_id)
    else:
        found = licenses.license_files(template)
        lic = licenses.classify_file(found[0]) if found else None
    if lic is None or not lic.spdx:
        raise CandidateError(
            "no licence: add a LICENSE file to the template, or pass --license with its SPDX id"
        )
    if lic.verdict != licenses.ALLOW_V:
        raise CandidateError(f"licence {lic.spdx} isn't allowed for a published template ({lic.verdict})")

    digests = {rel: _sha(p) for rel, p in files.items()}
    variables = _placeholders(files)
    cases = _checks(files)
    out.mkdir(parents=True)
    for rel, p in files.items():
        dest = out / "template" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
    listing = "\n".join(f"- `{rel}`" for rel in sorted(files)[:60]) + ("\n- …" if len(files) > 60 else "")
    fills = "\n".join(f"- `{v}`" for v in variables) or "- none: the files are used as they are"
    checks = "\n".join(f"- {c['id']}: `{c['command']}`" for c in cases)
    body = f"""# {name}

{description.strip()}

## Use it

1. Copy the files under `template/` into the new project.
2. Replace every placeholder below.
3. Run the checks, and keep the template's licence notice ({lic.spdx}).

## Placeholders

{fills}

## Checks

{checks}

## Files

{listing}

Template version {version}, digest `{tree_digest(digests)}` (see `provenance.json`).
"""
    (out / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {json.dumps(description.strip())}\nlicense: {lic.spdx}\n---\n\n{body}",
        encoding="utf-8",
    )
    provenance: dict[str, Any] = {
        "schema": PROVENANCE_SCHEMA,
        "template": template.name,
        "source_url": source_url,
        "version": version,
        "license": lic.spdx,
        "license_evidence": lic.evidence,
        "tree_digest": tree_digest(digests),
        "files": digests,
        "placeholders": variables,
        "wrapped_at": now_iso(),
    }
    (out / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    evaluation = {
        "schema": EVALUATION_SCHEMA,
        "finished_at": None,
        "cases": [{**c, "passed": None} for c in cases],
    }
    (out / EVALUATION_FILE).write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8")
    return out


__all__ = ["PROVENANCE_SCHEMA", "from_template", "tree_digest"]
