"""Install trove items into a tool's native layout (DESIGN.md §4.3)."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dex_trove import catalog, claude_compat, releases
from dex_trove.learn import EXEC_SUFFIXES, GENERATED
from dex_trove.paths import KIND_DIRS

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
    src: Path | None = None,
) -> list[Installed]:
    manifest = manifest or _Manifest(base)
    src = src or catalog.item_path(item)
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
        if (src / ".mcp.json").is_file():
            out += register_mcp(item, src / ".mcp.json", target=target, base=base, allow_exec=allow_exec)
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
    return [Installed(item["id"], kind, dest, notes=[f"adapted: {n}" for n in notes])]


def _mcp_servers(path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InstallError(f"{path}: not valid JSON ({exc})") from exc
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict) or not all(
        isinstance(v, dict) and v.get("command") for v in servers.values()
    ):
        raise InstallError(f"{path}: expected {{'mcpServers': {{name: {{'command': ..., 'args': [...]}}}}}}")
    return servers


def _pin(server: dict[str, Any]) -> dict[str, Any]:
    """Dex's own servers run the Dex version that installed them, not whatever is newest later."""
    from dex_trove import __version__

    args = [f"dex-trove=={__version__}" if a == "dex-trove" else a for a in server.get("args", [])]
    return {**server, "args": args}


def register_mcp(
    item: dict[str, Any], config: Path, *, target: str, base: Path, allow_exec: bool
) -> list[Installed]:
    """Adds a plugin's MCP servers to the project's client config: ``.mcp.json`` (Claude Code) or
    ``.vscode/mcp.json`` (VS Code / Copilot). A server is a command the client will start, so like a hook it needs
    ``--allow-exec``. Entries that exist already are left alone, and user-level configs are never edited."""
    servers = {name: _pin(spec) for name, spec in _mcp_servers(config).items()}
    names = ", ".join(sorted(servers))
    commands = [
        f"dex mcp config {n.removeprefix('dex-')} --client {'claude-code' if target == 'claude' else 'vscode'}"
        for n in sorted(servers)
        if n.startswith("dex-")
    ]
    hint = f" (or run: {'; '.join(commands)})" if commands else ""
    if not allow_exec:
        return [
            Installed(
                item["id"],
                "mcp",
                None,
                f"MCP server {names} runs a command — pass --allow-exec to register it{hint}",
            )
        ]
    if target == "claude" and base == Path.home() / ".claude":
        return [Installed(item["id"], "mcp", None, f"user scope: Dex doesn't edit ~/.claude.json{hint}")]
    if target == "claude":
        dest, key, stdio = base.parent / ".mcp.json", "mcpServers", False
    elif target == "copilot":
        dest, key, stdio = base.parent / ".vscode" / "mcp.json", "servers", True
    else:
        return [Installed(item["id"], "mcp", None, f"--target dir has no MCP client config{hint}")]
    current: dict[str, Any] = {}
    if dest.is_file():
        try:
            current = json.loads(dest.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise InstallError(f"{dest}: not valid JSON, so it was left alone ({exc})") from exc
    table = current.setdefault(key, {})
    if not isinstance(table, dict):
        raise InstallError(f"{dest}: '{key}' isn't an object, so it was left alone")
    added, kept = [], []
    for name, spec in sorted(servers.items()):
        if name in table:
            kept.append(name)
            continue
        table[name] = {"type": "stdio", **spec} if stdio else spec
        added.append(name)
    if added:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    notes = [f"registered {', '.join(added)}"] if added else []
    notes += [f"{n} was already configured; left unchanged" for n in kept]
    return [
        Installed(
            item["id"], "mcp", dest if added else None, "" if added else "already registered", notes=notes
        )
    ]


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


def install_locked(
    entries: list[releases.Locked],
    *,
    target: str,
    scope: str = "user",
    path: Path | None = None,
    allow_exec: bool = False,
    force: bool = False,
) -> list[Installed]:
    """Install exactly what a lock pins: the trove's copy when its digest matches, else the release fetched from Git."""
    if target not in TARGETS:
        raise InstallError(f"unknown target {target!r}; choose from {', '.join(TARGETS)}")
    items = catalog.load()
    current = {releases.key_of(it): it for it in items}
    base = _base(target, scope, path)
    manifest = _Manifest(base)
    out: list[Installed] = []
    try:
        with tempfile.TemporaryDirectory(prefix="dex-locked-") as tmp:
            for e in entries:
                kind, _, item_id = e.key.partition(":")
                it = current.get(e.key)
                if it is not None and it["content_hash"] == e.content_hash:
                    out += install_one(
                        it,
                        target=target,
                        base=base,
                        allow_exec=allow_exec,
                        items=items,
                        manifest=manifest,
                        force=force,
                    )
                    continue
                try:
                    src = releases.fetch(e, Path(tmp) / e.key.replace(":", "-").replace("/", "."))
                except releases.ReleaseError as exc:
                    out.append(Installed(item_id, kind, None, str(exc)))
                    continue
                ns, _, name = item_id.partition("/")
                pinned = {
                    **(it or {}),
                    "id": item_id,
                    "kind": kind,
                    "namespace": ns,
                    "name": name,
                    "entry": e.entry,
                    "files": e.files,
                    "version": e.version,
                    "content_hash": e.content_hash,
                    "executes_code": any(Path(r).suffix in EXEC_SUFFIXES for r in e.files)
                    or "hooks.json" in e.files,
                    "dir": f"{KIND_DIRS[kind]}/{ns}.{name}",
                }
                done = install_one(
                    pinned,
                    target=target,
                    base=base,
                    allow_exec=allow_exec,
                    items=items,
                    manifest=manifest,
                    force=force,
                    src=src,
                )
                for d in done:
                    d.notes.append(
                        f"pinned {e.version} fetched from {str(e.source.get('commit'))[:12]} and verified"
                    )
                out += done
    finally:
        manifest.save()
    return out


__all__ = ["GENERATED", "MANIFEST", "InstallError", "Installed", "install", "install_locked"]
