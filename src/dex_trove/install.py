"""Install trove items into a tool's native layout (DESIGN.md §4.3)."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dex_trove import catalog, claude_compat
from dex_trove.learn import GENERATED

TARGETS = ("claude", "copilot", "dir")
# What Dex installed under a base directory, so a re-install may replace its own unmodified copies but never a
# file or folder the user wrote (or edited after installing). Lives next to what it describes.
MANIFEST = ".dex-trove-installed.json"


class InstallError(RuntimeError):
    pass


@dataclass
class Installed:
    id: str
    kind: str
    dest: Path | None
    skipped: str = ""
    notes: list[str] = field(default_factory=list)


def _base(target: str, scope: str, path: Path | None) -> Path:
    if path is not None:
        return path.expanduser().resolve()
    if target == "claude":
        return (Path.home() / ".claude") if scope == "user" else Path.cwd() / ".claude"
    if target == "copilot":
        return Path.cwd() / ".github"
    raise InstallError("--path is required for --target dir")


SIDECARS = {"ananke.yaml", "dex.json"}  # trove metadata that installs leave behind


def _digest(path: Path, *, skip: frozenset[str] = frozenset()) -> str:
    h = hashlib.sha256()
    if path.is_dir():
        files = (q for q in path.rglob("*") if q.is_file() and "__pycache__" not in q.parts)
        for p in sorted(q for q in files if q.relative_to(path).as_posix() not in skip):
            h.update(p.relative_to(path).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    else:
        h.update(path.read_bytes())
    return h.hexdigest()


class _Manifest:
    def __init__(self, base: Path) -> None:
        self.path = base / MANIFEST
        try:
            self.entries: dict[str, dict[str, str]] = json.loads(self.path.read_text())["installed"]
        except (OSError, ValueError, KeyError, TypeError):
            self.entries = {}
        self.base = base

    def key(self, dest: Path) -> str:
        return dest.relative_to(self.base).as_posix()

    def owns(self, dest: Path) -> bool:
        rec = self.entries.get(self.key(dest))
        return rec is not None and rec.get("sha256") == _digest(dest)

    def record(self, dest: Path, item_id: str) -> None:
        self.entries[self.key(dest)] = {"id": item_id, "sha256": _digest(dest)}

    def save(self) -> None:
        if not self.entries:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = {"comment": "Written by `dex install`; lets it replace only its own copies.", "installed": {}}
        body["installed"] = dict(sorted(self.entries.items()))
        self.path.write_text(json.dumps(body, indent=2) + "\n")


def _blocked(dest: Path, manifest: _Manifest, force: bool, new_digest: str) -> str:
    """Why ``dest`` must not be replaced, or ``""`` when it may be.

    Replaceable: absent, recorded by Dex and unedited since, or byte-identical to what would be written (a copy
    made by an older Dex, before the manifest existed).
    """
    if dest.is_symlink():
        if force:
            dest.unlink()  # remove the link itself; never delete what it points to
            return ""
        return (
            f"{dest} is a symlink (probably your own skill) — not replaced; pass --force to replace the link"
        )
    if not dest.exists() or force or manifest.owns(dest) or _digest(dest) == new_digest:
        return ""
    return f"{dest} already exists and wasn't installed by Dex (or was edited since) — pass --force to replace it"


def _copy_dir(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=lambda _d, names: [n for n in names if n in SIDECARS])


def _entry_bytes(src_dir: Path, item: dict[str, Any], *, adapt_agent: bool) -> tuple[bytes, list[str]]:
    raw = (src_dir / item["entry"]).read_bytes()
    if not adapt_agent:
        return raw, []
    text, notes = claude_compat.adapt_agent(raw.decode("utf-8"))
    return text.encode("utf-8"), notes


def install_one(
    item: dict[str, Any],
    *,
    target: str,
    base: Path,
    allow_exec: bool,
    items: list[dict[str, Any]],
    manifest: _Manifest | None = None,
    force: bool = False,
) -> list[Installed]:
    manifest = manifest or _Manifest(base)
    src = catalog.item_path(item)
    kind, name = item["kind"], item["name"]
    if kind == "plugin":
        out: list[Installed] = []
        for member in item.get("members", []):
            out += install_one(
                catalog.resolve(items, member),
                target=target,
                base=base,
                allow_exec=allow_exec,
                items=items,
                manifest=manifest,
                force=force,
            )
        return out
    if item.get("executes_code") and kind == "hook" and not allow_exec:
        return [Installed(item["id"], kind, None, "hook runs code — pass --allow-exec after reviewing it")]
    if target == "dir":
        spec: tuple[str, Path] | None = ("dir", base / item["dir"])
    else:
        layout: dict[str, dict[str, tuple[str, Path]]] = {
            "claude": {
                "skill": ("dir", base / "skills" / name),
                "agent": ("entry", base / "agents" / f"{name}.md"),
                "prompt": ("entry", base / "commands" / f"{name}.md"),
            },
            "copilot": {
                "skill": ("dir", base / "skills" / name),
                "agent": ("entry", base / "agents" / f"{name}.agent.md"),
                "instruction": ("entry", base / "instructions" / f"{name}.instructions.md"),
                "prompt": ("entry", base / "prompts" / f"{name}.prompt.md"),
                "hook": ("dir", base / "hooks" / name),
                "workflow": ("entry", base / "workflows" / f"{name}.md"),
            },
        }
        spec = layout[target].get(kind)
    if spec is None:
        return [Installed(item["id"], kind, None, f"{kind} has no native {target} layout — use --target dir")]
    mode, dest = spec
    notes: list[str] = []
    if mode == "dir":
        new_digest = _digest(src, skip=frozenset(SIDECARS))
    else:
        data, notes = _entry_bytes(src, item, adapt_agent=target == "claude" and kind == "agent")
        new_digest = hashlib.sha256(data).hexdigest()
    reason = _blocked(dest, manifest, force, new_digest)
    if reason:
        return [Installed(item["id"], kind, None, reason)]
    if mode == "dir":
        _copy_dir(src, dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        lic = next((src / f for f in ("LICENSE.upstream",) if (src / f).is_file()), None)
        if lic is not None:
            shutil.copyfile(lic, dest.with_name(dest.name + ".LICENSE"))
    manifest.record(dest, item["id"])
    return [Installed(item["id"], kind, dest, notes=notes)]


def install(
    refs: list[str],
    *,
    target: str,
    scope: str = "user",
    path: Path | None = None,
    allow_exec: bool = False,
    force: bool = False,
) -> list[Installed]:
    if target not in TARGETS:
        raise InstallError(f"unknown target {target!r}; choose from {', '.join(TARGETS)}")
    items = catalog.load()
    if not items:
        raise InstallError("the trove catalog is empty — run `dex learn` (dev) or reinstall dex-trove")
    base = _base(target, scope, path)
    manifest = _Manifest(base)
    out: list[Installed] = []
    try:
        for ref in refs:
            out += install_one(
                catalog.resolve(items, ref),
                target=target,
                base=base,
                allow_exec=allow_exec,
                items=items,
                manifest=manifest,
                force=force,
            )
    finally:
        manifest.save()
    return out


__all__ = ["GENERATED", "MANIFEST", "InstallError", "Installed", "install"]
