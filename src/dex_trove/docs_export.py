"""Export the trove as Astro content: one Markdown page per item plus JSON indexes (DESIGN.md §10)."""

from __future__ import annotations

import json
import posixpath
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from dex_trove import catalog, frontmatter
from dex_trove.sources import Candidate, Source

MAX_BODY = 60_000
_REL = r"(?![a-z][a-z0-9+.-]*:|#|//)"  # relative, or root-relative (= upstream repo root)
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(" + _REL + r"([^)\s]+)((?:\s+\"[^\"]*\")?)\)", re.IGNORECASE)
_MD_LINK = re.compile(r"(?<!!)\[([^\]]*)\]\(" + _REL + r"([^)\s]+)((?:\s+\"[^\"]*\")?)\)", re.IGNORECASE)
_HTML_SRC = re.compile(r"""(<(?:img|source)\b[^>]*?\bsrc=)(["'])""" + _REL + r"""([^"']+)\2""", re.IGNORECASE)


def _bases(item: dict[str, Any]) -> tuple[tuple[str, str], str]:
    """``((raw, blob), item_dir)``: URL prefixes pinned to the learned commit, and the item's directory."""
    src = item["source"]
    repo, commit = src.get("repo") or "", src.get("commit")
    m = re.match(r"https://github\.com/([^/]+/[^/]+)", repo)
    item_dir = (
        src["path"] if item["entry"] != src["path"].rsplit("/", 1)[-1] else posixpath.dirname(src["path"])
    )
    if m and commit:
        return (
            f"https://raw.githubusercontent.com/{m.group(1)}/{commit}/",
            f"https://github.com/{m.group(1)}/blob/{commit}/",
        ), item_dir
    # First-party: link into this repo's trove copy.
    return (
        "https://raw.githubusercontent.com/Neo-Pragnya/Dex-Trove/main/",
        "https://github.com/Neo-Pragnya/Dex-Trove/blob/main/",
    ), f"trove/{item['dir']}"


def rewrite_relative(body: str, item: dict[str, Any]) -> str:
    """Relative image/link targets break on the site (and in Astro's asset pipeline): pin them upstream."""
    (raw, blob), item_dir = _bases(item)

    def target(prefix: str, rel: str) -> str:
        clean = rel.split("#")[0]
        path = posixpath.normpath(
            clean.lstrip("/") if clean.startswith("/") else posixpath.join(item_dir, clean)
        )
        frag = "#" + rel.split("#", 1)[1] if "#" in rel else ""
        return prefix + path + frag

    body = _MD_IMAGE.sub(lambda m: f"![{m.group(1)}]({target(raw, m.group(2))}{m.group(3)})", body)
    body = _MD_LINK.sub(lambda m: f"[{m.group(1)}]({target(blob, m.group(2))}{m.group(3)})", body)
    return _HTML_SRC.sub(lambda m: f"{m.group(1)}{m.group(2)}{target(raw, m.group(3))}{m.group(2)}", body)


def _body(trove: Path, item: dict[str, Any]) -> str:
    path = trove / item["dir"] / item["entry"]
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".json":
        return f"```json\n{text}\n```\n"
    _, body = frontmatter.split(text)
    # Drop a leading H1: the page renders its own title.
    body = re.sub(r"\A\s*#\s+[^\n]*\n", "", body, count=1)
    body = rewrite_relative(body, item)
    if len(body) > MAX_BODY:
        body = body[:MAX_BODY] + "\n\n*…truncated — see the upstream file for the rest.*\n"
    return body


_SKIP_META = {"name", "description", "license", "title"}
_GENERIC_TAGS = {
    "skill",
    "agent",
    "instruction",
    "prompt",
    "hook",
    "workflow",
    "plugin",
    "executes-code",
    "ananke-secret-flag",
}
_STOP = {
    "expert",
    "mode",
    "agent",
    "skill",
    "best",
    "practices",
    "guide",
    "development",
    "generator",
    "the",
    "and",
    "for",
    "with",
    "code",
    "instructions",
    "helper",
    "builder",
    "assistant",
}


def _flat(value: Any) -> str:
    """Upstream frontmatter values rendered for a metadata table."""
    if isinstance(value, list):
        return ", ".join(_flat(v) for v in value)
    if isinstance(value, dict):
        return "; ".join(f"{k}: {_flat(v)}" for k, v in value.items())
    return str(value)


def upstream_meta(trove: Path, item: dict[str, Any]) -> list[dict[str, str]]:
    path = trove / item["dir"] / item["entry"]
    if path.suffix != ".md" or not path.is_file():
        return []
    fm, _ = frontmatter.split(path.read_text(encoding="utf-8", errors="replace"))
    rows = []
    for key, value in fm.items():
        key = "on" if key == "True" else key  # YAML 1.1 reads the workflow key `on:` as a boolean
        if key in _SKIP_META or value in (None, "", [], {}):
            continue
        rows.append({"key": key, "value": _flat(value)[:600]})
    return rows


def hook_events(trove: Path, item: dict[str, Any]) -> list[dict[str, str]]:
    path = trove / item["dir"] / "hooks.json"
    if item["kind"] != "hook" or not path.is_file():
        return []
    try:
        hooks = json.loads(path.read_text(encoding="utf-8")).get("hooks", {})
    except (json.JSONDecodeError, AttributeError):
        return []
    rows = []
    for event, entries in hooks.items():
        for entry in entries if isinstance(entries, list) else []:
            cmd = entry.get("bash") or entry.get("powershell") or entry.get("command") or ""
            rows.append({"event": event, "command": str(cmd), "timeout": str(entry.get("timeoutSec", ""))})
    return rows


def file_rows(trove: Path, item: dict[str, Any]) -> list[dict[str, Any]]:
    (_, blob), item_dir = _bases(item)
    base = trove / item["dir"]
    rows = []
    for rel in item["files"]:
        f = base / rel
        upstream = (
            posixpath.join(item_dir, rel)
            if item["source"].get("commit") or not item["source"].get("repo")
            else ""
        )
        rows.append({"path": rel, "size": f.stat().st_size if f.is_file() else 0, "url": blob + upstream})
    return rows


def _tokens(item: dict[str, Any]) -> set[str]:
    return {t for t in re.split(r"[-._]", item["name"]) if len(t) >= 4 and t not in _STOP}


def relations(items: list[dict[str, Any]]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """``(related, part_of)``: up to six neighbours per item, and the plugins that bundle it."""
    part_of: dict[str, list[str]] = {}
    for it in items:
        for member in it.get("members", []):
            part_of.setdefault(member, []).append(f"plugin:{it['id']}")
    tags = {f"{i['kind']}:{i['id']}": set(i["tags"]) - _GENERIC_TAGS - {i["namespace"]} for i in items}
    toks = {f"{i['kind']}:{i['id']}": _tokens(i) for i in items}
    index: dict[str, set[str]] = {}
    for key in tags:
        for t in tags[key] | {f"~{x}" for x in toks[key]}:
            index.setdefault(t, set()).add(key)
    related: dict[str, list[str]] = {}
    for key in tags:
        scores: dict[str, int] = {}
        for t in tags[key]:
            for other in index.get(t, ()):
                scores[other] = scores.get(other, 0) + 2
        for t in toks[key]:
            for other in index.get(f"~{t}", ()):
                scores[other] = scores.get(other, 0) + 3
        scores.pop(key, None)
        best = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
        related[key] = [k for k, score in best if score >= 3]
    return related, part_of


def export(trove: Path, out: Path, sources: list[Source], candidates: list[Candidate]) -> int:
    items = catalog.load(trove)
    content = out / "content" / "items"
    data = out / "data"
    if content.exists():
        shutil.rmtree(content)
    content.mkdir(parents=True)
    data.mkdir(parents=True, exist_ok=True)
    slim = []
    related, part_of = relations(items)
    for it in items:
        key = f"{it['kind']}:{it['id']}"
        fm = {
            "id": it["id"],
            "kind": it["kind"],
            "namespace": it["namespace"],
            "name": it["name"],
            "title": it["title"],
            "description": it["description"],
            "tags": it["tags"],
            "version": it["version"],
            "license": it["license"],
            "source": it["source"],
            "inspired_by": it.get("inspired_by", []),
            "executes_code": it.get("executes_code", False),
            "members": it.get("members", []),
            "files": it["files"],
            "apply_to": it.get("apply_to"),
            "notes": it.get("notes", []),
            "upstream_meta": upstream_meta(trove, it),
            "hook_events": hook_events(trove, it),
            "file_rows": file_rows(trove, it),
            "related": related.get(key, []),
            "part_of": part_of.get(key, []),
            "secret_flags": len(it.get("secret_flags", [])),
        }
        page = (
            "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n" + _body(trove, it)
        )
        (content / f"{it['kind']}--{it['namespace']}.{it['name']}.md").write_text(page, encoding="utf-8")
        slim.append(
            {
                "id": it["id"],
                "kind": it["kind"],
                "ns": it["namespace"],
                "name": it["name"],
                "title": it["title"],
                "d": it["description"][:240],
                "tags": it["tags"],
                "lic": it["license"]["spdx"],
            }
        )
    (data / "search.json").write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")
    excluded_path = trove / "EXCLUDED.json"
    excluded = json.loads(excluded_path.read_text())["excluded"] if excluded_path.is_file() else []
    lock_path = trove / "trove.lock.json"
    lock = json.loads(lock_path.read_text())["sources"] if lock_path.is_file() else {}
    src_rows = []
    for s in sources:
        src_rows.append(
            {
                "id": s.id,
                "title": s.title,
                "description": s.description,
                "url": s.web_url,
                "adapter": s.adapter,
                "enabled": s.enabled,
                "first_party": s.first_party,
                "lock": lock.get(s.id),
                "licenses": sorted({i["license"]["spdx"] for i in items if i["namespace"] == s.id}),
            }
        )
    meta = {
        "sources": src_rows,
        "candidates": [c.__dict__ for c in candidates],
        "excluded": excluded,
        "counts": {k: sum(1 for i in items if i["kind"] == k) for k in sorted({i["kind"] for i in items})},
        "total": len(items),
    }
    (data / "trove.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(items)
