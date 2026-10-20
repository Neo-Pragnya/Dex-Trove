"""The learn pipeline: adapt → licence → guard → normalise → write (DESIGN.md §4–§7)."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from dex_trove import ignore, licenses
from dex_trove.adapters import ADAPTERS, JUNK_DIRS, RawItem
from dex_trove.licenses import ALLOW_V, DENY_V, REVIEW_V, Classification
from dex_trove.paths import DIR_KINDS, KIND_DIRS
from dex_trove.sources import Source

KIND_TO_ANANKE = {
    "skill": "skill",
    "agent": "agent",
    "instruction": "prompt",
    "prompt": "prompt",
    "hook": "tool",
    "workflow": "workflow",
    "plugin": "bundle",
}
GENERATED = {"ananke.yaml", "dex.json", "LICENSE.upstream", "NOTICE.upstream"}
JUNK_FILES = {".DS_Store", "Thumbs.db", ".gitkeep"}
EXEC_SUFFIXES = {".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd", ".py", ".js", ".mjs", ".cjs", ".ts"}
CANONICAL_TEXTS = Path(__file__).parent / "license_texts"
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ITEM_BYTES = 20 * 1024 * 1024
_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$")
_SEMVER = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?$")
SECRET_PATTERNS = {
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private-key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----\s*\n[A-Za-z0-9+/=]{40,}"),
    "github-token": re.compile(r"\b(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{60,}\b"),
    "slack-token": re.compile(r"\bxox[abpr]-[0-9]{8,}-[A-Za-z0-9-]{10,}\b"),
    "anthropic-key": re.compile(r"\bsk-ant-api\d{2}-[A-Za-z0-9_-]{40,}\b"),
    "openai-key": re.compile(r"\bsk-proj-[A-Za-z0-9_-]{40,}\b"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
}
# Mirror of Ananke's registration-time scanner (ananke.plexus.registry.secrets). It is deliberately broad,
# so security-teaching content trips it on placeholders; Dex records those as flags instead of excluding.
ANANKE_SECRET_RULES = {
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private-key": re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "pypi-token": re.compile(r"\bpypi-[A-Za-z0-9_\-]{40,}\b"),
    "slack-token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "bearer-token": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{24,}\b"),
    "openai-key": re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
    "generic-credential": re.compile(
        r"""(?ix)\b(?:api[_-]?key|secret|token|passwd|password)\b\s*[:=]\s*
        ['"]?(?!\$\{|<|\{\{|your[_-]|example|changeme|xxx|\*\*\*)[A-Za-z0-9_\-/+=]{16,}['"]?"""
    ),
}
_SECRET_ALLOW = re.compile(r"EXAMPLE|XXXX|xxxx|your[_-]?|<|\.\.\.")


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def slugify(name: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", name.strip())
    s = re.sub(r"[^a-z0-9.-]+", "-", s.lower()).strip("-.")
    s = re.sub(r"-{2,}", "-", s)
    return s[:64].rstrip("-.")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class Exclusion:
    source: str
    kind: str
    name: str
    path: str
    reason: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return self.__dict__.copy()


@dataclass
class SourceResult:
    source: Source
    commit: str | None
    items: list[dict[str, Any]] = field(default_factory=list)
    excluded: list[Exclusion] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    ignored: int = 0  # skipped by .dexignore rules; deliberately not recorded anywhere else


# --------------------------------------------------------------------------- licence resolution
@dataclass
class LicenseDecision:
    cls: Classification
    text_file: Path | None = None  # the governing licence text, if any
    notice_file: Path | None = None


def _first_recognised(directory: Path, root: Path) -> tuple[Classification, Path] | None:
    for f in licenses.license_files(directory):
        rel = f.relative_to(root).as_posix() if f.is_relative_to(root) else f.name
        cls = licenses.classify_file(f, label=rel)
        if cls.spdx:
            return cls, f
    return None


def _notice_near(start: Path, root: Path) -> Path | None:
    d = start
    while True:
        for name in ("NOTICE", "NOTICE.txt", "NOTICE.md"):
            if (d / name).is_file():
                return d / name
        if d == root or d.parent == d or not d.is_relative_to(root):
            return None
        d = d.parent


def resolve_license(raw: RawItem, source: Source, root: Path) -> LicenseDecision:
    """Most specific evidence wins; any deny evidence at item level wins outright (DESIGN.md §5)."""
    fm = licenses.classify_frontmatter(raw.meta.get("license"))
    own: list[tuple[Classification, Path]] = []
    if raw.is_dir:
        for f in licenses.license_files(raw.path):
            own.append((licenses.classify_file(f, label=f.relative_to(root).as_posix()), f))
    for cls, f in own:
        if cls.verdict == DENY_V:
            return LicenseDecision(cls, f)
    if fm and fm.verdict == DENY_V:
        return LicenseDecision(fm)
    ancestors: list[tuple[Classification, Path]] = []
    d = raw.path.parent
    while d.is_relative_to(root):
        hit = _first_recognised(d, root)
        if hit:
            ancestors.append(hit)
            break
        if d == root:
            break
        d = d.parent
    if fm:
        text = next((f for c, f in own if c.spdx == fm.spdx), None) or next(
            (f for c, f in ancestors if c.spdx == fm.spdx), None
        )
        notice = licenses.copyright_lines(text.read_text(errors="replace")) if text else ""
        cls = Classification(fm.spdx, fm.verdict, fm.evidence, notice)
        return LicenseDecision(cls, text, _notice_near(raw.item_dir, root))
    for cls, f in own:
        if cls.spdx:
            return LicenseDecision(cls, f, _notice_near(raw.item_dir, root))
    if ancestors:
        cls, f = ancestors[0]
        return LicenseDecision(cls, f, _notice_near(raw.item_dir, root))
    if source.first_party and source.default_license:
        spdx, verdict = licenses.evaluate_expression(source.default_license)
        return LicenseDecision(
            Classification(spdx, verdict, "first-party default (sources.yaml)", "Copyright (c) Neo Pragnya")
        )
    return LicenseDecision(Classification(None, DENY_V, "no licence found"))


# --------------------------------------------------------------------------- guards
def collect_files(raw: RawItem, source: Source, root: Path) -> tuple[dict[str, Path], list[str]]:
    notes: list[str] = []
    if not raw.is_dir:
        return {raw.path.name: raw.path}, notes
    files: dict[str, Path] = {}
    dropped = 0
    for dirpath, dirnames, filenames in os.walk(raw.path):
        base = Path(dirpath)
        keep = []
        for d in sorted(dirnames):
            p = base / d
            if d in JUNK_DIRS:
                continue
            if p.is_symlink():
                notes.append(f"skipped symlinked dir {p.relative_to(raw.path).as_posix()}")
                continue
            keep.append(d)
        dirnames[:] = keep
        for fn in sorted(filenames):
            p = base / fn
            rel = p.relative_to(raw.path).as_posix()
            src_rel = p.relative_to(root).as_posix()
            if fn in JUNK_FILES or fn.endswith(".pyc") or fn in GENERATED:
                continue
            if any(fnmatch.fnmatch(src_rel, pat) for pat in source.exclude):
                dropped += 1
                continue
            if p.is_symlink():
                notes.append(f"skipped symlink {rel}")
                continue
            files[rel] = p
    if dropped:
        notes.append(f"{dropped} file(s) withheld by sources.yaml exclude globs (third-party terms)")
    return files, notes


def scan_secrets(files: dict[str, Path]) -> str | None:
    for rel, p in files.items():
        if p.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            for m in pattern.finditer(text):
                if not _SECRET_ALLOW.search(m.group(0)):
                    return f"{label} in {rel}"
    return None


def ananke_secret_flags(files: dict[str, Path]) -> list[str]:
    """``rule path:line`` for each line Ananke's scanner would refuse (no secret text is recorded)."""
    flags = []
    for rel, p in files.items():
        if p.stat().st_size > 1_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for rule, pattern in ANANKE_SECRET_RULES.items():
                if pattern.search(line):
                    flags.append(f"{rule} {rel}:{lineno}")
    return flags


# --------------------------------------------------------------------------- versions
def _semver(value: str | None) -> str | None:
    if not value:
        return None
    m = _SEMVER.match(value.strip())
    if not m:
        return None
    return f"{int(m.group(1))}.{int(m.group(2))}.{int(m.group(3) or 0)}"


def _bump_patch(version: str) -> str:
    major, minor, patch = (int(x) for x in version.split(".")[:3])
    return f"{major}.{minor}.{patch + 1}"


def _summary(text: str, limit: int = 200) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    dot = cut.rfind(". ")
    return (cut[: dot + 1] if dot > 80 else cut.rstrip() + "…").strip()


# --------------------------------------------------------------------------- the pipeline
class Learner:
    def __init__(self, trove: Path, *, dry_run: bool = False) -> None:
        self.trove = trove
        self.dry_run = dry_run
        self.catalog_before = {r["id"]: r for r in read_catalog(trove)}

    def item_dir(self, kind: str, ns: str, slug: str) -> Path:
        return self.trove / KIND_DIRS[kind] / f"{ns}.{slug}"

    def learn(
        self, source: Source, root: Path, commit: str | None, priority_of: dict[str, int]
    ) -> SourceResult:
        result = SourceResult(source, commit)
        ns = source.id
        # Hashes owned by higher-priority sources win duplicates (DESIGN.md §6).
        seen: dict[str, str] = {
            r["entry_hash"]: r["id"]
            for r in self.catalog_before.values()
            if r.get("entry_hash") and priority_of.get(r["namespace"], 1 << 30) < source.priority
        }
        produced: dict[tuple[str, str], dict[str, Any]] = {}
        plugins: list[RawItem] = []
        patterns = ignore.load_patterns(ns, root)
        for raw in ADAPTERS[source.adapter](root, source.options):
            rel = raw.path.relative_to(root).as_posix()
            if ignore.is_ignored([raw.name, slugify(raw.name)], rel, patterns):
                result.ignored += 1
                continue
            if raw.kind == "plugin":
                plugins.append(raw)
                continue
            self._one(raw, source, root, commit, seen, produced, result)
        for raw in plugins:
            members = []
            for kind, name in raw.members:
                rec = produced.get((kind, slugify(name)))
                if rec:
                    members.append(
                        {"ref": f"ananke://{KIND_TO_ANANKE[kind]}/{ns}/{rec['name']}", "version": "*"}
                    )
            if not members:
                self._exclude(
                    result, raw, root, "out-of-scope", "plugin has no admissible skill/agent members"
                )
                continue
            raw.members = [(k, slugify(n)) for k, n in raw.members if (k, slugify(n)) in produced]
            self._one(raw, source, root, commit, seen, produced, result, ananke_members=members)
        if not self.dry_run:
            keep = {self.item_dir(r["kind"], ns, r["name"]) for r in result.items}
            for kind_dir in KIND_DIRS.values():
                for d in sorted((self.trove / kind_dir).glob(f"{ns}.*")):
                    if d.is_dir() and d not in keep:
                        result.removed.append(f"{DIR_KINDS[kind_dir]}:{ns}/{d.name[len(ns) + 1 :]}")
                        shutil.rmtree(d)
        return result

    def _exclude(self, result: SourceResult, raw: RawItem, root: Path, reason: str, detail: str = "") -> None:
        result.excluded.append(
            Exclusion(
                source=result.source.id,
                kind=raw.kind,
                name=slugify(raw.name) or raw.name,
                path=raw.path.relative_to(root).as_posix(),
                reason=reason,
                detail=detail,
            )
        )

    def _one(
        self,
        raw: RawItem,
        source: Source,
        root: Path,
        commit: str | None,
        seen: dict[str, str],
        produced: dict[tuple[str, str], dict[str, Any]],
        result: SourceResult,
        *,
        ananke_members: list[dict[str, str]] | None = None,
    ) -> None:
        ns = source.id
        slug = slugify(raw.name)
        if not _NAME_RE.match(slug or ""):
            self._exclude(result, raw, root, "invalid-name", raw.name)
            return
        if (raw.kind, slug) in produced:
            self._exclude(result, raw, root, "name-collision", f"{ns}/{slug} already learned")
            return
        decision = resolve_license(raw, source, root)
        verdict = decision.cls.verdict
        if verdict == REVIEW_V and source.allow_review:
            verdict = ALLOW_V
        if verdict != ALLOW_V:
            reason = "license-review" if verdict == REVIEW_V else "license-denied"
            self._exclude(
                result, raw, root, reason, f"{decision.cls.spdx or 'unknown'} — {decision.cls.evidence}"
            )
            return
        files, notes = collect_files(raw, source, root)
        if raw.entry not in files:
            self._exclude(result, raw, root, "missing-entry", raw.entry)
            return
        big = [r for r, p in files.items() if p.stat().st_size > MAX_FILE_BYTES]
        total = sum(p.stat().st_size for p in files.values())
        if big or total > MAX_ITEM_BYTES:
            self._exclude(result, raw, root, "size", ", ".join(big) or f"{total} bytes")
            return
        components: set[str] = set()
        for rel, p in files.items():
            if "/" not in rel or not licenses.NESTED_LICENSE_RE.search(Path(rel).name):
                continue
            nested = licenses.classify_file(p, label=f"{raw.path.relative_to(root).as_posix()}/{rel}")
            nv = ALLOW_V if nested.verdict == REVIEW_V and source.allow_review else nested.verdict
            if nv != ALLOW_V:
                reason = "license-review" if nv == REVIEW_V else "license-denied"
                self._exclude(
                    result, raw, root, reason, f"bundled {nested.spdx or 'unknown'} — {nested.evidence}"
                )
                return
            components.add(nested.spdx or "unknown")
        secret = scan_secrets(files)
        if secret:
            self._exclude(result, raw, root, "secret", secret)
            return
        hashes = {rel: sha256_bytes(p.read_bytes()) for rel, p in sorted(files.items())}
        entry_hash = hashes[raw.entry]
        if entry_hash in seen:
            self._exclude(result, raw, root, "duplicate", f"same content as {seen[entry_hash]}")
            return
        content_hash = sha256_bytes(json.dumps(hashes, sort_keys=True).encode())
        dest = self.item_dir(raw.kind, ns, slug)
        prior = (
            self.catalog_before.get(f"{ns}/{slug}")
            if (self.catalog_before.get(f"{ns}/{slug}", {}).get("kind") == raw.kind)
            else None
        )
        upstream_version = _semver(raw.version)
        if prior and prior.get("content_hash") == content_hash:
            version, learned_at = prior["version"], prior["learned_at"]
        else:
            learned_at = now_iso()
            if upstream_version:
                version = upstream_version
            elif prior:
                version = _bump_patch(prior["version"])
            else:
                version = "1.0.0"
        rel_path = raw.path.relative_to(root).as_posix()
        url = source.upstream_url(commit, rel_path, raw.is_dir)
        if url is None and source.first_party and source.homepage:
            url = f"{source.homepage}/tree/main/trove/{KIND_DIRS[raw.kind]}/{ns}.{slug}"
        executes = any(Path(r).suffix in EXEC_SUFFIXES for r in files) or "hooks.json" in files
        secret_flags = ananke_secret_flags(files)
        tags = sorted(
            set(raw.tags)
            | {raw.kind, ns}
            | ({"executes-code"} if executes else set())
            | ({"ananke-secret-flag"} if secret_flags else set())
        )
        overrides = source.items.get(slug, {}) or source.items.get(raw.name, {}) or {}
        description = raw.description or _summary(raw.body, 400)
        record: dict[str, Any] = {
            "id": f"{ns}/{slug}",
            "kind": raw.kind,
            "namespace": ns,
            "name": slug,
            "title": str(overrides.get("title") or raw.title or slug),
            "description": description,
            "tags": tags,
            "version": version,
            "entry": raw.entry,
            "dir": f"{KIND_DIRS[raw.kind]}/{ns}.{slug}",
            "source": {
                "id": ns,
                "title": source.title,
                "repo": source.web_url,
                "commit": commit,
                "path": rel_path,
                "url": url,
                "author": raw.author,
            },
            "license": {
                "spdx": decision.cls.spdx,
                "verdict": verdict,
                "evidence": decision.cls.evidence,
                "notice": decision.cls.notice,
                "components": sorted(components - {decision.cls.spdx}),
            },
            "inspired_by": list(overrides.get("inspired_by", [])),
            "executes_code": executes,
            "members": [f"{k}:{ns}/{n}" for k, n in raw.members],
            "files": sorted(hashes),
            "entry_hash": entry_hash,
            "content_hash": content_hash,
            "learned_at": learned_at,
        }
        if secret_flags:
            record["secret_flags"] = secret_flags
        if raw.meta.get("applyTo"):
            record["apply_to"] = str(raw.meta["applyTo"])
        if notes:
            record["notes"] = notes
        seen[entry_hash] = record["id"]
        produced[(raw.kind, slug)] = record
        result.items.append(record)
        if self.dry_run:
            return
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        for rel, p in files.items():
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)
        if decision.text_file and not (raw.is_dir and decision.text_file.is_relative_to(raw.path)):
            shutil.copyfile(decision.text_file, dest / "LICENSE.upstream")
        elif not decision.text_file and (CANONICAL_TEXTS / f"{decision.cls.spdx}.txt").is_file():
            # Declared (e.g. frontmatter) but no text shipped upstream: Apache §4(a) needs a copy.
            shutil.copyfile(CANONICAL_TEXTS / f"{decision.cls.spdx}.txt", dest / "LICENSE.upstream")
        if decision.notice_file and not (raw.is_dir and decision.notice_file.is_relative_to(raw.path)):
            shutil.copyfile(decision.notice_file, dest / "NOTICE.upstream")
        (dest / "ananke.yaml").write_text(
            yaml.safe_dump(
                ananke_manifest(record, ananke_members), sort_keys=False, allow_unicode=True, width=110
            ),
            encoding="utf-8",
        )
        (dest / "dex.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )


def ananke_manifest(record: dict[str, Any], members: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """An Ananke ``ArtifactManifest`` (strict schema: unknown fields are rejected)."""
    kind = KIND_TO_ANANKE[record["kind"]]
    manifest: dict[str, Any] = {
        "kind": kind,
        "namespace": record["namespace"],
        "name": record["name"],
        "version": record["version"],
        "ananke_id": f"urn:dex-trove:{record['kind']}:{record['namespace']}:{record['name']}",
        "summary": _summary(record["description"] or record["title"]),
        "description": record["description"],
        "runtime": {"supported": ["claude-code", "github-copilot", "generic"]},
    }
    if kind in {"agent", "prompt"}:
        manifest["instructions"] = {"ref": record["entry"]}
    if not record.get("executes_code"):
        # Pure instructions: declare "needs nothing" explicitly. Code-bearing items stay undeclared so
        # Ananke keeps warning until someone reviews them.
        manifest["permissions"] = {
            "filesystem": {"read": [], "write": []},
            "shell": {"allow": []},
            "network": [],
        }
    if members:
        manifest["members"] = members
    manifest["license"] = {
        "expression": record["license"]["spdx"],
        "source": record["license"]["evidence"][:200],
        "approval": "approved",
    }
    meta: dict[str, Any] = {"tags": record["tags"]}
    if record["source"].get("url"):
        meta["homepage"] = record["source"]["url"]
    if record["source"].get("repo"):
        meta["repository"] = record["source"]["repo"]
    manifest["metadata"] = meta
    return manifest


# --------------------------------------------------------------------------- trove-wide files
def read_catalog(trove: Path) -> list[dict[str, Any]]:
    path = trove / "catalog.json"
    if not path.is_file():
        return []
    items: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8")).get("items", [])
    return items


def rebuild_catalog(trove: Path) -> list[dict[str, Any]]:
    """Catalog = every ``dex.json`` on disk (so it can never drift from the items)."""
    items = []
    for kind_dir in KIND_DIRS.values():
        for f in sorted((trove / kind_dir).glob("*/dex.json")):
            items.append(json.loads(f.read_text(encoding="utf-8")))
    items.sort(key=lambda r: (r["kind"], r["id"]))
    return items


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def finalize(trove: Path, results: list[SourceResult], sources: list[Source]) -> dict[str, Any]:
    from dex_trove import __version__

    items = rebuild_catalog(trove)
    write_json(
        trove / "catalog.json", {"generator": f"dex-trove {__version__}", "count": len(items), "items": items}
    )

    excluded_path = trove / "EXCLUDED.json"
    prev = json.loads(excluded_path.read_text()).get("excluded", []) if excluded_path.is_file() else []
    learned = {r.source.id for r in results}
    excluded = [e for e in prev if e["source"] not in learned]
    for r in results:
        excluded += [e.as_dict() for e in r.excluded]
    excluded.sort(key=lambda e: (e["source"], e["kind"], e["name"]))
    write_json(excluded_path, {"count": len(excluded), "excluded": excluded})

    lock_path = trove / "trove.lock.json"
    lock = json.loads(lock_path.read_text()) if lock_path.is_file() else {"sources": {}}
    for r in results:
        counts: dict[str, int] = {}
        for it in r.items:
            counts[it["kind"]] = counts.get(it["kind"], 0) + 1
        lock["sources"][r.source.id] = {
            "repo": r.source.web_url,
            "ref": r.source.ref,
            "commit": r.commit,
            "learned_at": now_iso(),
            "items": dict(sorted(counts.items())),
            "excluded": len(r.excluded),
        }
    known = {s.id for s in sources}
    lock["sources"] = {k: v for k, v in sorted(lock["sources"].items()) if k in known}
    write_json(lock_path, lock)
    return {"items": len(items), "excluded": len(excluded)}
