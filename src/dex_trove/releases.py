"""Immutable releases, project locks and pinned fetches (docs/concepts/provenance-and-versioning.md).

The trove holds only the *current* bytes of each item. Every version it ever shipped is recorded in
``trove/releases.json``, an append-only ledger: version, content digest, the exact upstream commit and path, and
any fork parent. A release is never edited after it is written. Yanking and deprecating add a marker; they don't
change the bytes or the digest.

A project lock (``dex.lock.json``) pins items to a version and digest. Installing a lock uses the trove's bytes when
the digest matches the current release, and otherwise fetches that release from its upstream Git commit and checks
the digest before writing anything (a decentralised Git index; no hosted backend). A mismatch is an error, never a
fallback to another version or a similarly named item.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LEDGER_FILE = "releases.json"
LEDGER_SCHEMA = "dex-trove/releases@1"
LOCK_FILE = "dex.lock.json"
LOCK_SCHEMA = "dex-trove/lock@1"
CHANNELS = ("stable", "preview")
# Fields of a release that may change after it is written; everything else is immutable.
MUTABLE = frozenset({"yanked", "deprecated"})
_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


class ReleaseError(RuntimeError):
    pass


def key_of(item: dict[str, Any]) -> str:
    return f"{item['kind']}:{item['id']}"


def semver_key(version: str) -> tuple[int, int, int, str]:
    m = _SEMVER.match(version)
    if not m:
        return (0, 0, 0, version)
    return (int(m[1]), int(m[2]), int(m[3]), version)


def content_hash(files: dict[str, bytes]) -> str:
    """The digest ``dex learn`` records: SHA-256 over the sorted map of per-file SHA-256s."""
    hashes = {rel: hashlib.sha256(data).hexdigest() for rel, data in sorted(files.items())}
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


# --------------------------------------------------------------------------- the ledger
def load(trove: Path) -> dict[str, Any]:
    path = trove / LEDGER_FILE
    if not path.is_file():
        return {"schema": LEDGER_SCHEMA, "items": {}}
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != LEDGER_SCHEMA:
        raise ReleaseError(f"{path}: unknown schema {data.get('schema')!r}")
    return data


def save(trove: Path, ledger: dict[str, Any]) -> None:
    ledger["items"] = dict(sorted(ledger["items"].items()))
    path = trove / LEDGER_FILE
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def history(ledger: dict[str, Any], key: str) -> list[dict[str, Any]]:
    entry = ledger["items"].get(key)
    return list(entry["releases"]) if entry else []


def unique_version(ledger: dict[str, Any], key: str, version: str, digest: str) -> str:
    """``version`` unless the ledger already used it for different bytes; then the next free patch version.

    Upstreams sometimes change a file without bumping its declared version. Reusing the number would make one
    version mean two contents, so Dex moves on instead.
    """
    used = {r["version"]: r["content_hash"] for r in history(ledger, key)}
    if used.get(version, digest) == digest:
        return version
    top = max((semver_key(v) for v in used), default=semver_key(version))
    major, minor, patch = top[:3]
    candidate = f"{major}.{minor}.{patch + 1}"
    while candidate in used:
        patch += 1
        candidate = f"{major}.{minor}.{patch + 1}"
    return candidate


def record(ledger: dict[str, Any], items: list[dict[str, Any]]) -> list[str]:
    """Append a release for every item whose current digest isn't the latest release. Returns what changed."""
    changed: list[str] = []
    live = {key_of(it) for it in items}
    for it in items:
        key = key_of(it)
        entry = ledger["items"].setdefault(key, {"releases": []})
        entry.pop("removed", None)
        rels = entry["releases"]
        if rels and rels[-1]["content_hash"] == it["content_hash"] and rels[-1]["version"] == it["version"]:
            continue
        if any(r["version"] == it["version"] and r["content_hash"] != it["content_hash"] for r in rels):
            raise ReleaseError(f"{key}: version {it['version']} already released with other content")
        src = it.get("source", {})
        release: dict[str, Any] = {
            "version": it["version"],
            "content_hash": it["content_hash"],
            "entry": it["entry"],
            "files": list(it["files"]),
            "source": {"repo": src.get("repo"), "commit": src.get("commit"), "path": src.get("path")},
            "released_at": it["learned_at"],
            "channel": "stable",
        }
        parent = it.get("forked_from")
        if parent:
            release["parent"] = parent
        if any(r["content_hash"] == it["content_hash"] for r in rels):
            release["note"] = "returns to the content of an earlier release"
        rels.append(release)
        changed.append(f"{key}@{it['version']}")
    for key, entry in ledger["items"].items():
        if key not in live and "removed" not in entry:
            entry["removed"] = True  # history stays; pinned locks can still fetch these versions
            changed.append(f"{key} removed from the trove (history kept)")
    return changed


def _find(ledger: dict[str, Any], key: str, version: str) -> dict[str, Any]:
    for r in history(ledger, key):
        if r["version"] == version:
            return r
    raise ReleaseError(f"{key} has no release {version}")


def resolve(ledger: dict[str, Any], key: str, version: str | None = None) -> dict[str, Any]:
    """An exact release. Without ``version``: the newest stable, non-yanked one (never a mutable 'latest' pin)."""
    rels = history(ledger, key)
    if not rels:
        raise ReleaseError(f"{key} has no releases")
    if version:
        if version.startswith("sha256:"):
            hits = [r for r in rels if r["content_hash"] == version.removeprefix("sha256:")]
            if not hits:
                raise ReleaseError(f"{key} has no release with digest {version}")
            return hits[-1]
        return _find(ledger, key, version)
    ok = [r for r in rels if not r.get("yanked") and r.get("channel", "stable") == "stable"]
    if not ok:
        raise ReleaseError(f"every release of {key} is yanked or unstable; pin one explicitly")
    return max(ok, key=lambda r: semver_key(r["version"]))


def yank(ledger: dict[str, Any], key: str, version: str, reason: str, *, at: str) -> None:
    if not reason.strip():
        raise ReleaseError("a yank needs a reason")
    _find(ledger, key, version)["yanked"] = {"reason": reason, "at": at}


def unyank(ledger: dict[str, Any], key: str, version: str) -> None:
    _find(ledger, key, version).pop("yanked", None)


def deprecate(
    ledger: dict[str, Any],
    key: str,
    reason: str,
    *,
    at: str,
    replaced_by: str | None = None,
    version: str | None = None,
) -> None:
    if not reason.strip():
        raise ReleaseError("a deprecation needs a reason")
    if replaced_by and replaced_by not in ledger["items"]:
        raise ReleaseError(f"replacement {replaced_by} is not in the ledger")
    mark = {"reason": reason, "at": at, **({"replaced_by": replaced_by} if replaced_by else {})}
    targets = [_find(ledger, key, version)] if version else history(ledger, key)
    if not targets:
        raise ReleaseError(f"{key} has no releases")
    for r in targets:
        r["deprecated"] = mark


def lineage(ledger: dict[str, Any], key: str) -> dict[str, Any]:
    """Fork ancestry (parents, nearest first) and direct children of ``key``."""
    parents: list[dict[str, Any]] = []
    seen = {key}
    cur = key
    while True:
        rels = history(ledger, cur)
        parent = next((r["parent"] for r in reversed(rels) if r.get("parent")), None)
        if not parent or parent["key"] in seen:
            break
        parents.append(parent)
        seen.add(parent["key"])
        cur = parent["key"]
    children = sorted(
        k
        for k, e in ledger["items"].items()
        if any((r.get("parent") or {}).get("key") == key for r in e["releases"])
    )
    return {"key": key, "parents": parents, "children": children}


def problems(
    ledger: dict[str, Any], items: list[dict[str, Any]], previous: dict[str, Any] | None = None
) -> list[str]:
    """Ledger consistency, and immutability against an earlier copy of the ledger when one is given."""
    out: list[str] = []
    current = {key_of(it): it for it in items}
    for key, entry in ledger["items"].items():
        rels = entry["releases"]
        versions = [r["version"] for r in rels]
        if len(set(versions)) != len(versions):
            out.append(f"{key}: a version appears twice in its release history")
        if [semver_key(v) for v in versions] != sorted(semver_key(v) for v in versions):
            out.append(f"{key}: releases are not in version order")
        for r in rels:
            if r.get("channel", "stable") not in CHANNELS:
                out.append(f"{key}@{r['version']}: unknown channel {r.get('channel')!r}")
            parent = r.get("parent")
            if parent and parent.get("key") not in ledger["items"]:
                out.append(f"{key}@{r['version']}: fork parent {parent.get('key')} is not in the ledger")
            rep = (r.get("deprecated") or {}).get("replaced_by")
            if rep and rep not in ledger["items"]:
                out.append(f"{key}@{r['version']}: replaced_by {rep} is not in the ledger")
        it = current.get(key)
        if it is None:
            if not entry.get("removed"):
                out.append(f"{key}: in the ledger but not the trove, and not marked removed")
        elif (
            not rels or rels[-1]["content_hash"] != it["content_hash"] or rels[-1]["version"] != it["version"]
        ):
            out.append(
                f"{key}: the current item isn't the latest release — run `dex learn` or `dex release record`"
            )
    missing = sorted(set(current) - set(ledger["items"]))
    out += [f"{k}: no release recorded" for k in missing[:20]]
    if len(missing) > 20:
        out.append(f"… and {len(missing) - 20} more items without releases")
    if previous is not None:
        out += immutability_problems(previous, ledger)
    return out


def _immutable(release: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in release.items() if k not in MUTABLE}


def immutability_problems(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """A release, once written, keeps every field except the yank and deprecation markers, and is never deleted."""
    out: list[str] = []
    for key, entry in before.get("items", {}).items():
        now = {r["version"]: r for r in after.get("items", {}).get(key, {}).get("releases", [])}
        for r in entry["releases"]:
            n = now.get(r["version"])
            if n is None:
                out.append(f"{key}@{r['version']}: release deleted")
                continue
            if _immutable(r) != _immutable(n):
                out.append(f"{key}@{r['version']}: released metadata changed (releases are immutable)")
    return out


# --------------------------------------------------------------------------- project locks
@dataclass
class Locked:
    key: str
    version: str
    content_hash: str
    source: dict[str, Any]
    entry: str
    files: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "version": self.version,
            "content_hash": self.content_hash,
            "entry": self.entry,
            "files": self.files,
            "source": self.source,
        }


def lock_entry(key: str, release: dict[str, Any]) -> Locked:
    return Locked(
        key,
        release["version"],
        release["content_hash"],
        release["source"],
        release["entry"],
        release["files"],
    )


def read_lock(path: Path) -> list[Locked]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReleaseError(f"cannot read lock {path}: {exc}") from exc
    if data.get("schema") != LOCK_SCHEMA:
        raise ReleaseError(f"{path}: not a Dex lock (schema {data.get('schema')!r})")
    return [Locked(**e) for e in data.get("items", [])]


def write_lock(path: Path, entries: list[Locked], *, generator: str) -> None:
    body = {
        "schema": LOCK_SCHEMA,
        "generator": generator,
        "comment": "Pins Dex Trove items to an exact version and digest. Install it with `dex install --locked`.",
        "items": [e.as_dict() for e in sorted(entries, key=lambda e: e.key)],
    }
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def check_lock(ledger: dict[str, Any], entries: list[Locked]) -> tuple[list[str], list[str]]:
    """``(errors, warnings)`` for a lock against the ledger. Yanked pins still resolve but warn."""
    errors: list[str] = []
    warnings: list[str] = []
    for e in entries:
        try:
            rel = _find(ledger, e.key, e.version)
        except ReleaseError as exc:
            errors.append(str(exc))
            continue
        if rel["content_hash"] != e.content_hash:
            errors.append(f"{e.key}@{e.version}: the lock's digest differs from the released digest")
        if rel.get("yanked"):
            warnings.append(f"{e.key}@{e.version} is yanked: {rel['yanked']['reason']}")
        if rel.get("deprecated"):
            rep = rel["deprecated"].get("replaced_by")
            warnings.append(
                f"{e.key}@{e.version} is deprecated: {rel['deprecated']['reason']}"
                + (f" (use {rep})" if rep else "")
            )
    return errors, warnings


# --------------------------------------------------------------------------- pinned fetch from upstream Git
def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=300)


def fetch(entry: Locked, dest: Path) -> Path:
    """Materialise a pinned release from its upstream commit into ``dest`` and verify its digest.

    Only the release's own files are written. Nothing is written to ``dest`` unless the digest matches.
    """
    src = entry.source
    repo, commit, path = src.get("repo"), src.get("commit"), src.get("path")
    if not repo or not commit or path is None:
        raise ReleaseError(
            f"{entry.key}@{entry.version} has no upstream commit to fetch from; install the dex-trove version "
            "that shipped it, or re-lock to the current release"
        )
    with tempfile.TemporaryDirectory(prefix="dex-fetch-") as tmp:
        work = Path(tmp)
        try:
            _git("init", "-q", cwd=work)
            _git("remote", "add", "origin", repo, cwd=work)
            _git("fetch", "-q", "--depth", "1", "origin", commit, cwd=work)
            _git("checkout", "-q", "FETCH_HEAD", "--", path, cwd=work)
        except (subprocess.SubprocessError, FileNotFoundError) as exc:
            raise ReleaseError(
                f"{entry.key}@{entry.version}: cannot fetch {repo}@{commit[:12]}: {exc}"
            ) from exc
        root = work / path
        single = root.is_file()
        files: dict[str, bytes] = {}
        for rel in entry.files:
            f = root if single else root / rel
            if not f.is_file():
                raise ReleaseError(f"{entry.key}@{entry.version}: {rel} is missing upstream at {commit[:12]}")
            files[rel] = f.read_bytes()
        got = content_hash(files)
        if got != entry.content_hash:
            raise ReleaseError(
                f"{entry.key}@{entry.version}: upstream bytes don't match the released digest "
                f"(expected {entry.content_hash[:12]}, got {got[:12]}); refusing to install"
            )
        if dest.exists():
            shutil.rmtree(dest)
        for rel, data in files.items():
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
    return dest


__all__ = [
    "LEDGER_FILE",
    "LOCK_FILE",
    "Locked",
    "ReleaseError",
    "check_lock",
    "content_hash",
    "deprecate",
    "fetch",
    "history",
    "immutability_problems",
    "key_of",
    "lineage",
    "load",
    "lock_entry",
    "problems",
    "read_lock",
    "record",
    "resolve",
    "save",
    "unique_version",
    "unyank",
    "write_lock",
    "yank",
]
