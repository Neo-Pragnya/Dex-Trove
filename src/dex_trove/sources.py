"""``sources.yaml`` loading and fetching upstream repos at a pinned commit."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from dex_trove.paths import cache_dir, sources_file


@dataclass
class Source:
    id: str
    title: str
    adapter: str
    repo: str | None = None
    ref: str = "HEAD"
    local: str | None = None
    enabled: bool = True
    first_party: bool = False
    default_license: str | None = None
    allow_review: bool = False
    priority: int = 0
    homepage: str | None = None
    description: str = ""
    options: dict[str, Any] = field(default_factory=dict)
    exclude: list[str] = field(default_factory=list)
    items: dict[str, dict[str, Any]] = field(default_factory=dict)  # per-item overrides (inspired_by…)
    notes: str = ""

    @property
    def web_url(self) -> str | None:
        if self.repo:
            return re.sub(r"\.git$", "", self.repo)
        return self.homepage

    def upstream_url(self, commit: str | None, rel: str, is_dir: bool) -> str | None:
        """Link to the item upstream; ``None`` when the source isn't a public repo (first-party folders)."""
        base = self.web_url if self.repo else None
        if not base or "github.com" not in base:
            return base
        kind = "tree" if is_dir else "blob"
        return f"{base}/{kind}/{commit or self.ref}/{rel}".rstrip("/")


@dataclass
class Candidate:
    """A repo evaluated for the trove but not (yet) enabled — shown on the docs Sources page."""

    repo: str
    license: str
    decision: str
    offers: str = ""


def load(path: Path | None = None) -> tuple[list[Source], list[Candidate]]:
    data = yaml.safe_load((path or sources_file()).read_text(encoding="utf-8")) or {}
    sources: list[Source] = []
    for i, raw in enumerate(data.get("sources", [])):
        lic = raw.get("license", {}) or {}
        sources.append(
            Source(
                id=raw["id"],
                title=raw.get("title", raw["id"]),
                adapter=raw["adapter"],
                repo=raw.get("repo"),
                ref=raw.get("ref", "HEAD"),
                local=raw.get("local"),
                enabled=raw.get("enabled", True),
                first_party=bool(lic.get("first_party", False)),
                default_license=lic.get("default"),
                allow_review=bool(lic.get("allow_review", False)),
                priority=i,
                homepage=raw.get("homepage"),
                description=raw.get("description", ""),
                options=raw.get("options", {}) or {},
                exclude=raw.get("exclude", []) or [],
                items=raw.get("items", {}) or {},
                notes=raw.get("notes", ""),
            )
        )
    candidates = [Candidate(**c) for c in data.get("candidates", [])]
    return sources, candidates


def _git(*args: str, cwd: Path | None = None) -> str:
    out = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return out.stdout.strip()


def git_commit(path: Path) -> str | None:
    try:
        return _git("rev-parse", "HEAD", cwd=path)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def fetch(source: Source, *, prefer_local: bool = False, refresh: bool = True) -> tuple[Path, str | None]:
    """Materialise a source on disk. Returns ``(root, commit)``; commit is ``None`` for non-git folders."""
    if source.local and (prefer_local or not source.repo):
        root = Path(source.local).expanduser()
        if not root.is_absolute():
            root = (sources_file().parent / root).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"source {source.id}: local path {root} does not exist")
        return root, git_commit(root)
    if not source.repo:
        raise ValueError(f"source {source.id} has neither repo nor local")
    dest = cache_dir() / "sources" / source.id
    if dest.is_dir() and (dest / ".git").is_dir():
        if refresh:
            ref = source.ref if source.ref != "HEAD" else "HEAD"
            _git("fetch", "--depth", "1", "origin", ref, cwd=dest)
            _git("reset", "--hard", "FETCH_HEAD", cwd=dest)
    else:
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        args = ["clone", "--depth", "1"]
        if source.ref != "HEAD":
            args += ["--branch", source.ref]
        _git(*args, source.repo, str(dest))
    return dest, git_commit(dest)
