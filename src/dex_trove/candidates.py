"""Reviewed learning candidates: the only way new or improved capability memory enters a source.

A candidate is a skill folder that a harness (Ananke) or a person proposes, with an evaluation report and a review
decision beside it. ``dex candidate publish`` refuses unless every gate passes:

1. the folder is a well-formed skill (``SKILL.md`` with a name and description), within the size limits;
2. its licence is declared and allowed, and no secret-shaped text is present;
3. the evaluation report has at least one positive and one regression case, and every case passed;
4. a reviewer approved it (``review.json``), after the evaluation;
5. an internal-only candidate never goes to a public source.

Publishing copies the folder into the chosen source's local folder. It doesn't change any installed or locked copy:
``dex learn`` then records a new immutable release, and existing locks keep their pinned version.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dex_trove import licenses
from dex_trove.frontmatter import split as split_frontmatter
from dex_trove.learn import (
    MAX_FILE_BYTES,
    MAX_ITEM_BYTES,
    ananke_secret_flags,
    now_iso,
    scan_secrets,
    slugify,
)
from dex_trove.sources import Source

EVALUATION_FILE = "evaluation.json"
EVALUATION_SCHEMA = "dex-trove/evaluation@1"
REVIEW_FILE = "review.json"
VISIBILITIES = ("public", "internal")
GATE_FILES = frozenset({EVALUATION_FILE, REVIEW_FILE})  # evidence beside the candidate, never published


class CandidateError(RuntimeError):
    pass


@dataclass
class Report:
    name: str
    visibility: str
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "visibility": self.visibility,
            "ok": self.ok,
            "passed": self.passed,
            "failed": self.failed,
        }


def _files(path: Path) -> dict[str, Path]:
    return {
        p.relative_to(path).as_posix(): p
        for p in sorted(path.rglob("*"))
        if p.is_file() and p.name not in GATE_FILES and "__pycache__" not in p.parts and not p.is_symlink()
    }


def _evaluation(path: Path, report: Report) -> str | None:
    """Check the evaluation; return when it finished (ISO time) so the review can be checked against it."""
    f = path / EVALUATION_FILE
    if not f.is_file():
        report.failed.append(f"no {EVALUATION_FILE}: a candidate needs evaluation evidence")
        return None
    try:
        ev = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as exc:
        report.failed.append(f"{EVALUATION_FILE} is not JSON: {exc}")
        return None
    if ev.get("schema") != EVALUATION_SCHEMA:
        report.failed.append(f"{EVALUATION_FILE}: schema must be {EVALUATION_SCHEMA}")
        return None
    cases = ev.get("cases") or []
    kinds = {c.get("kind") for c in cases}
    if "positive" not in kinds or "regression" not in kinds:
        report.failed.append("evaluation needs at least one positive and one regression case")
    failing = [str(c.get("id", "?")) for c in cases if c.get("passed") is not True]
    if failing:
        report.failed.append(f"evaluation cases failed: {', '.join(failing[:5])}")
    if cases and not failing and {"positive", "regression"} <= kinds:
        report.passed.append(f"evaluation: {len(cases)} case(s) passed")
    finished = ev.get("finished_at")
    return str(finished) if finished else None


def check(path: Path, *, visibility: str = "public") -> Report:
    """Run every gate except review and destination. Never raises for a bad candidate; reports instead."""
    if visibility not in VISIBILITIES:
        raise CandidateError(f"visibility must be one of {', '.join(VISIBILITIES)}")
    path = path.resolve()
    report = Report(path.name, visibility)
    skill_md = path / "SKILL.md"
    if not skill_md.is_file():
        report.failed.append("no SKILL.md: only skills can be candidates today")
        return report
    meta, _ = split_frontmatter(skill_md.read_text(encoding="utf-8"))
    name, description = str(meta.get("name") or ""), str(meta.get("description") or "")
    if not name or slugify(name) != name:
        report.failed.append("SKILL.md needs a lowercase-hyphen `name`")
    else:
        report.name = name
    if len(description) < 40:
        report.failed.append("SKILL.md needs a `description` that says what it does and when to use it")
    if name and description and len(description) >= 40:
        report.passed.append("skill: name and description present")
    files = _files(path)
    big = [r for r, p in files.items() if p.stat().st_size > MAX_FILE_BYTES]
    if big or sum(p.stat().st_size for p in files.values()) > MAX_ITEM_BYTES:
        report.failed.append(f"too large: {', '.join(big) or 'total size'}")
    lic = licenses.classify_frontmatter(meta.get("license"))
    if lic is None:
        found = licenses.license_files(path)
        lic = licenses.classify_file(found[0]) if found else None
    if lic is None:
        report.failed.append("no licence declared (frontmatter `license` or a LICENSE file)")
    elif lic.verdict != licenses.ALLOW_V:
        report.failed.append(f"licence {lic.spdx or 'unknown'} is not allowed ({lic.verdict})")
    else:
        report.passed.append(f"licence: {lic.spdx}")
    secret = scan_secrets(files)
    flags = ananke_secret_flags(files)
    if secret or flags:
        report.failed.append(f"secret-shaped text: {secret or '; '.join(flags[:3])}")
    else:
        report.passed.append("no secret-shaped text")
    finished = _evaluation(path, report)
    if finished:
        report.passed.append(f"evaluated at {finished}")
    return report


def review(path: Path, *, approve: bool, reviewer: str, reason: str) -> dict[str, Any]:
    if not reviewer.strip() or not reason.strip():
        raise CandidateError("a review needs a reviewer and a reason")
    decision = {
        "decision": "approved" if approve else "rejected",
        "reviewer": reviewer,
        "reason": reason,
        "at": now_iso(),
    }
    (path / REVIEW_FILE).write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
    return decision


def _review_ok(path: Path, report: Report) -> None:
    f = path / REVIEW_FILE
    if not f.is_file():
        report.failed.append("not reviewed: run `dex candidate review --approve` first")
        return
    rv = json.loads(f.read_text(encoding="utf-8"))
    if rv.get("decision") != "approved":
        report.failed.append(f"review {rv.get('decision', 'missing')}: {rv.get('reason', '')}".strip())
        return
    ev = path / EVALUATION_FILE
    if ev.is_file() and ev.stat().st_mtime > f.stat().st_mtime:
        report.failed.append("the evaluation changed after the review; review it again")
        return
    report.passed.append(f"approved by {rv.get('reviewer')}")


def publish(path: Path, source: Source, *, visibility: str = "public") -> Path:
    """Copy an approved, passing candidate into ``source``'s local folder. Raises with every failed gate."""
    report = check(path, visibility=visibility)
    _review_ok(path.resolve(), report)
    if visibility == "internal" and source.visibility != "internal":
        report.failed.append(f"internal-only candidate cannot go to public source {source.id}")
    if not source.local:
        report.failed.append(f"source {source.id} has no local folder to publish into")
    if not report.ok:
        raise CandidateError("; ".join(report.failed))
    from dex_trove.paths import sources_file

    root = Path(str(source.local)).expanduser()
    if not root.is_absolute():
        root = (sources_file().parent / root).resolve()
    dest = root / report.name
    if dest.exists():
        shutil.rmtree(
            dest
        )  # an update: `dex learn` records it as a new version; history is kept in the ledger
    dest.mkdir(parents=True)
    for rel, p in _files(path.resolve()).items():
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
    return dest


__all__ = ["CandidateError", "Report", "check", "publish", "review"]
