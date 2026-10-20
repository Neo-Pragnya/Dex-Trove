"""Install trove items into a tool's native layout (DESIGN.md §4.3)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dex_trove import catalog
from dex_trove.learn import GENERATED

TARGETS = ("claude", "copilot", "dir")


class InstallError(RuntimeError):
    pass


@dataclass
class Installed:
    id: str
    kind: str
    dest: Path | None
    skipped: str = ""


def _base(target: str, scope: str, path: Path | None) -> Path:
    if path is not None:
        return path.expanduser().resolve()
    if target == "claude":
        return (Path.home() / ".claude") if scope == "user" else Path.cwd() / ".claude"
    if target == "copilot":
        return Path.cwd() / ".github"
    raise InstallError("--path is required for --target dir")


def _copy_dir(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        src, dest, ignore=lambda _d, names: [n for n in names if n in {"ananke.yaml", "dex.json"}]
    )


def _copy_entry(src_dir: Path, item: dict[str, Any], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_dir / item["entry"], dest)


def install_one(
    item: dict[str, Any], *, target: str, base: Path, allow_exec: bool, items: list[dict[str, Any]]
) -> list[Installed]:
    src = catalog.item_path(item)
    kind, name = item["kind"], item["name"]
    if kind == "plugin":
        out: list[Installed] = []
        for member in item.get("members", []):
            out += install_one(
                catalog.resolve(items, member), target=target, base=base, allow_exec=allow_exec, items=items
            )
        return out
    if item.get("executes_code") and kind == "hook" and not allow_exec:
        return [Installed(item["id"], kind, None, "hook runs code — pass --allow-exec after reviewing it")]
    if target == "dir":
        dest = base / item["dir"]
        _copy_dir(src, dest)
        return [Installed(item["id"], kind, dest)]
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
    if mode == "dir":
        _copy_dir(src, dest)
    else:
        _copy_entry(src, item, dest)
        lic = next((src / f for f in ("LICENSE.upstream",) if (src / f).is_file()), None)
        if lic is not None:
            shutil.copyfile(lic, dest.with_name(dest.name + ".LICENSE"))
    return [Installed(item["id"], kind, dest)]


def install(
    refs: list[str], *, target: str, scope: str = "user", path: Path | None = None, allow_exec: bool = False
) -> list[Installed]:
    if target not in TARGETS:
        raise InstallError(f"unknown target {target!r}; choose from {', '.join(TARGETS)}")
    items = catalog.load()
    if not items:
        raise InstallError("the trove catalog is empty — run `dex learn` (dev) or reinstall dex-trove")
    base = _base(target, scope, path)
    out: list[Installed] = []
    for ref in refs:
        out += install_one(
            catalog.resolve(items, ref), target=target, base=base, allow_exec=allow_exec, items=items
        )
    return out


__all__ = ["GENERATED", "InstallError", "Installed", "install"]
