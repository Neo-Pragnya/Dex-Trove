"""Adapt Copilot-style agent frontmatter to Claude Code at install time.

The trove keeps upstream bytes; only the installed copy changes. Two fields decide whether Claude Code can launch
a subagent at all (https://code.claude.com/docs/en/sub-agents):

- ``tools``: Claude tool names. "If no entry in the list resolves to a tool, the subagent usually fails to
  launch", and VS Code ids such as ``codebase`` or ``edit/editFiles`` resolve to nothing.
- ``model``: ``sonnet``, ``opus``, ``haiku``, ``fable``, a full Claude model ID, or ``inherit``. ``GPT-4.1`` is none.

Tools map through a fixed table. Ids without a Claude equivalent (IDE panels, VS Code APIs, MCP servers) are
dropped and reported, never guessed. When an upstream list maps to nothing, the agent gets the read-only
``Read, Grep, Glob`` instead of inheriting every tool: a missing mapping must not widen what an agent can do.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from dex_trove import frontmatter

# VS Code / Copilot tool id (lower-cased) → Claude Code tools. Absent ids have no safe equivalent.
TOOL_MAP: dict[str, tuple[str, ...]] = {
    **dict.fromkeys(
        ["read", "read/readfile", "readfile", "codebase", "search/codebase"], ("Read", "Grep", "Glob")
    ),
    **dict.fromkeys(
        [
            "search",
            "searchresults",
            "search/searchresults",
            "search/filesearch",
            "search/textsearch",
            "search/listdirectory",
            "findtestfiles",
            "usages",
            "search/usages",
        ],
        ("Grep", "Glob"),
    ),
    **dict.fromkeys(
        ["edit", "edit/editfiles", "editfiles", "new", "edit/createfile", "edit/createdirectory"],
        ("Edit", "Write"),
    ),
    **dict.fromkeys(
        [
            "runcommands",
            "execute",
            "execute/runinterminal",
            "runinterminal",
            "terminalcommand",
            "execute/getterminaloutput",
            "terminallastcommand",
            "read/terminallastcommand",
            "terminalselection",
            "read/terminalselection",
            "runtests",
            "execute/runtests",
            "testfailure",
            "execute/testfailure",
            "runtasks",
            "execute/createandruntask",
        ],
        ("Bash",),
    ),
    **dict.fromkeys(["fetch", "web/fetch"], ("WebFetch",)),
    "web": ("WebFetch", "WebSearch"),
    "websearch": ("WebSearch",),
}
CLAUDE_TOOLS = {"Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebFetch", "WebSearch", "NotebookEdit"}
READ_ONLY = ("Read", "Grep", "Glob")
CLAUDE_MODELS = {"sonnet", "opus", "haiku", "fable", "inherit"}
MARKER = "# dex-trove: adapted for Claude Code at install; the trove keeps the upstream file unchanged"


def _tool_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [t.strip().strip("'\"") for t in value.strip("[]").split(",") if t.strip()]
    return []


def map_tools(upstream: list[str]) -> tuple[list[str], list[str]]:
    """Return ``(claude_tools, unmapped_ids)`` in a stable order."""
    out: list[str] = []
    unmapped: list[str] = []
    for tool in upstream:
        if tool in CLAUDE_TOOLS:  # already a Claude tool name
            mapped: tuple[str, ...] = (tool,)
        else:
            mapped = TOOL_MAP.get(tool.lower(), ())
        if not mapped:
            unmapped.append(tool)
        out += [m for m in mapped if m not in out]
    return out, unmapped


def map_model(value: Any) -> str | None:
    """A Claude model value, or ``None`` to drop the field (Claude Code then picks its default)."""
    text = str(value or "").strip()
    if not text:
        return None
    if text in CLAUDE_MODELS or re.fullmatch(r"claude-[a-z0-9.-]+", text):
        return text
    family = re.search(r"\b(opus|sonnet|haiku|fable)\b", text.lower())
    return family.group(1) if family and "claude" in text.lower() else None


def adapt_agent(text: str) -> tuple[str, list[str]]:
    """Return ``(adapted_text, notes)``. The body after the frontmatter is kept byte-for-byte."""
    fm, body = frontmatter.split(text)
    if not fm:
        return text, []
    notes: list[str] = []
    changed = dict(fm)
    if "tools" in fm:
        upstream = _tool_list(fm["tools"])
        tools, unmapped = map_tools(upstream)
        if unmapped:
            notes.append(
                f"dropped {len(unmapped)} tool id(s) with no Claude equivalent: {', '.join(unmapped)}"
            )
        if upstream and not tools:
            tools = list(READ_ONLY)
            notes.append("no listed tool maps to Claude Code; limited to read-only Read, Grep, Glob")
        if tools:
            changed["tools"] = ", ".join(tools)
        else:
            del changed["tools"]
    if "model" in fm:
        model = map_model(fm["model"])
        if model is None:
            del changed["model"]
            notes.append(f"dropped model {fm['model']!r} (not a Claude model; Claude Code picks the default)")
        elif model != fm["model"]:
            changed["model"] = model
            notes.append(f"model {fm['model']!r} → {model!r}")
    if changed == fm:
        return text, []
    head = yaml.safe_dump(changed, sort_keys=False, allow_unicode=True, width=10_000).rstrip("\n")
    return f"---\n{MARKER}\n{head}\n---\n{body}", notes


__all__ = ["MARKER", "TOOL_MAP", "adapt_agent", "map_model", "map_tools"]
