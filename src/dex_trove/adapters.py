"""Adapters turn an upstream layout into raw items (DESIGN.md §3, §4.3).

An adapter only *finds* things; licence, guards and normalisation happen in :mod:`dex_trove.learn`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dex_trove import frontmatter

JUNK_DIRS = {".git", "__pycache__", "node_modules", ".venv", ".github", ".DS_Store"}


@dataclass
class RawItem:
    kind: str
    name: str
    path: Path  # item directory, or the single file for file-items
    entry: str  # entry file name (relative to the item directory)
    is_dir: bool
    meta: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    version: str | None = None
    author: str | None = None
    members: list[tuple[str, str]] = field(default_factory=list)  # (kind, raw name) for plugins

    @property
    def item_dir(self) -> Path:
        return self.path if self.is_dir else self.path.parent


def _read_md(path: Path) -> tuple[dict[str, Any], str]:
    return frontmatter.split(path.read_text(encoding="utf-8", errors="replace"))


def _str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return str(value.get("name") or "")
    return str(value).strip()


def _md_item(kind: str, path: Path, *, name: str | None = None, is_dir: bool, entry: str) -> RawItem:
    meta, body = _read_md(path)
    raw_name = _str(meta.get("name")) if kind == "skill" else ""
    stem = name or raw_name or (path.parent.name if is_dir else path.name.split(".")[0])
    title = _str(meta.get("title")) or (_str(meta.get("name")) if kind != "skill" else "")
    return RawItem(
        kind=kind,
        name=stem,
        path=path.parent if is_dir else path,
        entry=entry,
        is_dir=is_dir,
        meta=meta,
        body=body,
        title=title or frontmatter.first_heading(body) or stem,
        description=_str(meta.get("description")),
        tags=frontmatter.as_tags(meta.get("tags") or meta.get("keywords")),
        version=_str(meta.get("version")) or None,
        author=_str(meta.get("author")) or None,
    )


def _walk_skill_dirs(root: Path) -> Iterator[Path]:
    """Every directory holding a ``SKILL.md``; does not descend into a skill once found."""
    if not root.is_dir():
        return
    if (root / "SKILL.md").is_file():
        yield root
        return
    for child in sorted(root.iterdir()):
        if child.is_dir() and not child.is_symlink() and child.name not in JUNK_DIRS:
            if child.name.startswith(".") and child.name not in {".curated", ".system", ".experimental"}:
                continue
            yield from _walk_skill_dirs(child)


def agent_skills(root: Path, options: dict[str, Any]) -> Iterator[RawItem]:
    """Agent Skills spec layout: any directory with ``SKILL.md`` under ``options.roots``."""
    for rel in options.get("roots", ["."]):
        for d in _walk_skill_dirs(root / rel):
            yield _md_item("skill", d / "SKILL.md", is_dir=True, entry="SKILL.md")


def md_agents(root: Path, options: dict[str, Any]) -> Iterator[RawItem]:
    """Markdown files with ``name``/``description`` frontmatter (Claude Code subagents and similar)."""
    kind = options.get("kind", "agent")
    for pattern in options.get("globs", ["agents/**/*.md"]):
        for path in sorted(root.glob(pattern)):
            if path.name.lower() in {"readme.md", "contributing.md", "changelog.md"} or not path.is_file():
                continue
            meta, _ = _read_md(path)
            if not meta.get("description"):
                continue
            yield _md_item(kind, path, is_dir=False, entry=path.name)


def _stem(ref: str) -> str:
    name = Path(ref.rstrip("/")).name
    return re.sub(r"(\.agent)?\.md$", "", name)


def awesome_copilot(root: Path, options: dict[str, Any]) -> Iterator[RawItem]:
    """github/awesome-copilot: skills, agents, instructions, prompts, hooks, workflows, plugins."""
    yield from agent_skills(root, {"roots": ["skills"]})
    for path in sorted((root / "agents").glob("*.agent.md")):
        yield _md_item("agent", path, name=path.name[: -len(".agent.md")], is_dir=False, entry=path.name)
    for path in sorted((root / "instructions").glob("*.instructions.md")):
        name = path.name[: -len(".instructions.md")]
        yield _md_item("instruction", path, name=name, is_dir=False, entry=path.name)
    for path in sorted((root / "prompts").glob("*.prompt.md")):
        yield _md_item("prompt", path, name=path.name[: -len(".prompt.md")], is_dir=False, entry=path.name)
    for d in sorted(p for p in (root / "hooks").glob("*") if p.is_dir()):
        if (d / "README.md").is_file() and (d / "hooks.json").is_file():
            item = _md_item("hook", d / "README.md", name=d.name, is_dir=True, entry="README.md")
            item.title = _str(item.meta.get("name")) or item.title
            yield item
    for path in sorted((root / "workflows").glob("*.md")):
        item = _md_item("workflow", path, name=path.stem, is_dir=False, entry=path.name)
        item.title = _str(item.meta.get("name")) or item.title
        yield item
    for d in sorted(p for p in (root / "plugins").glob("*") if p.is_dir()):
        manifest = d / "plugin.json"
        if not manifest.is_file():
            continue
        data = json.loads(manifest.read_text(encoding="utf-8"))
        ext = (data.get("extensions") or {}).get("com.github.awesome-copilot") or {}
        members = [("skill", _stem(s)) for s in ext.get("skills", [])]
        members += [("agent", _stem(a)) for a in ext.get("agents", [])]
        has_readme = (d / "README.md").is_file()
        meta, body = _read_md(d / "README.md") if has_readme else ({}, "")
        yield RawItem(
            kind="plugin",
            name=data.get("name") or d.name,
            path=d,
            entry="README.md" if has_readme else "plugin.json",
            is_dir=True,
            meta={**meta, **{k: data.get(k) for k in ("license", "homepage", "repository")}},
            body=body,
            title=frontmatter.first_heading(body) or data.get("name") or d.name,
            description=_str(data.get("description")),
            tags=frontmatter.as_tags(data.get("keywords")),
            version=_str(data.get("version")) or None,
            author=_str(data.get("author")) or None,
            members=members,
        )


ADAPTERS: dict[str, Callable[[Path, dict[str, Any]], Iterator[RawItem]]] = {
    "agent-skills": agent_skills,
    "md-agents": md_agents,
    "awesome-copilot": awesome_copilot,
}
