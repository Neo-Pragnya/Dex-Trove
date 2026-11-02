"""Install checks: what Dex verified itself, kept apart from what an upstream says about itself.

``dex check-installs`` installs every item into each tool layout it supports, in a scratch directory, and checks
the installed files against what that tool needs to load them. The results go to ``trove/install-checks.json``
with the Dex version that ran them. They are *verified* facts. Claims in an item's own metadata (``compatibility``,
``metadata``, tags) are *self-reported* and shown separately. Dex collects no download or usage telemetry, so it
never reports install counts.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

from dex_trove import catalog, claude_compat, frontmatter
from dex_trove.install import install_one

CHECKS_FILE = "install-checks.json"
TARGETS = ("claude", "copilot")
_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HOOK_EVENTS = {
    "sessionStart", "sessionEnd", "userPromptSubmitted", "preToolUse", "postToolUse", "errorOccurred",
    "agentStop", "subagentStop",
}  # fmt: skip


def _meta(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        meta, _ = frontmatter.split(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        return None, f"frontmatter unreadable: {str(exc).splitlines()[0]}"
    return meta, ""


def _skill(dest: Path) -> list[str]:
    meta, err = _meta(dest / "SKILL.md")
    if meta is None:
        return [err]
    problems = []
    name, desc = str(meta.get("name") or ""), str(meta.get("description") or "")
    if not _NAME.match(name) or len(name) > 64:
        problems.append("SKILL.md name must be lowercase-hyphen, at most 64 characters")
    if not desc:
        problems.append("SKILL.md has no description, so it can never trigger")
    elif len(desc) > 1024:
        problems.append("SKILL.md description is longer than 1024 characters")
    return problems


def _claude_agent(dest: Path) -> list[str]:
    meta, err = _meta(dest)
    if meta is None:
        return [err]
    problems = []
    if not meta.get("description"):
        problems.append("agent has no description, so Claude Code can't choose it")
    tools = meta.get("tools")
    if tools is not None:
        listed = [
            t.strip() for t in (tools if isinstance(tools, list) else str(tools).split(",")) if str(t).strip()
        ]
        if listed and not any(t in claude_compat.CLAUDE_TOOLS or t.startswith("mcp__") for t in listed):
            problems.append("no listed tool exists in Claude Code, so the subagent can't launch")
    model = meta.get("model")
    if model and str(model) not in claude_compat.CLAUDE_MODELS and not str(model).startswith("claude-"):
        problems.append(f"model {model!r} isn't a Claude model")
    return problems


def _copilot_entry(kind: str, dest: Path) -> list[str]:
    meta, err = _meta(dest)
    if meta is None:
        return [err]
    if kind == "agent" and not meta.get("description"):
        return ["agent has no description"]
    if kind == "instruction" and not meta.get("applyTo"):
        return ["instruction has no applyTo glob, so it never applies"]
    # YAML 1.1 reads a bare `on:` key as the boolean True, which the frontmatter parser may stringify.
    if kind == "workflow" and not {str(k) for k in meta} & {"on", "True"}:
        return ["workflow has no `on:` trigger"]
    return []


def _hook(dest: Path) -> list[str]:
    try:
        data = json.loads((dest / "hooks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"hooks.json unreadable: {exc}"]
    events = set((data.get("hooks") or {}).keys())
    unknown = sorted(events - HOOK_EVENTS)
    return (
        [f"unknown hook event(s): {', '.join(unknown)}"]
        if unknown
        else ([] if events else ["no hook events"])
    )


def check_item(item: dict[str, Any], items: list[dict[str, Any]], target: str, work: Path) -> str | None:
    """``"pass"``, ``"fail: …"``, or ``None`` when the target has no layout for this kind."""
    base = work / target / item["kind"] / item["id"].replace("/", ".")
    done = install_one(item, target=target, base=base, allow_exec=True, items=items, force=True)
    placed = [d for d in done if d.dest is not None]
    if not placed:
        return None if all("no native" in d.skipped for d in done) else f"fail: {done[0].skipped}"
    problems: list[str] = []
    for d in placed:
        kind, dest = d.kind, Path(str(d.dest))
        if kind == "skill":
            problems += _skill(dest)
        elif kind == "agent" and target == "claude":
            problems += _claude_agent(dest)
        elif kind == "hook":
            problems += _hook(dest)
        elif kind in ("agent", "instruction", "workflow"):
            problems += _copilot_entry(kind, dest)
    return "fail: " + "; ".join(sorted(set(problems))[:3]) if problems else "pass"


def run(trove: Path, *, generator: str) -> dict[str, Any]:
    items = catalog.load(trove)
    results: dict[str, dict[str, str]] = {}
    with tempfile.TemporaryDirectory(prefix="dex-check-") as tmp:
        for it in items:
            row = {}
            for target in TARGETS:
                verdict = check_item(it, items, target, Path(tmp))
                if verdict is not None:
                    row[target] = verdict
            results[f"{it['kind']}:{it['id']}"] = row
    summary = {t: {"pass": 0, "fail": 0} for t in TARGETS}
    for row in results.values():
        for t, v in row.items():
            summary[t]["pass" if v == "pass" else "fail"] += 1
    return {"generator": generator, "summary": summary, "items": dict(sorted(results.items()))}


def write(trove: Path, data: dict[str, Any]) -> None:
    (trove / CHECKS_FILE).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def load(trove: Path) -> dict[str, Any]:
    path = trove / CHECKS_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"items": {}}


__all__ = ["CHECKS_FILE", "TARGETS", "check_item", "load", "run", "write"]
