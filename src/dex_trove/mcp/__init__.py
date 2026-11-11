"""Local MCP servers that ship with Dex: run with ``dex mcp serve NAME``, list with ``dex mcp list``.

Each server is a module with ``NAME``, ``TITLE``, ``INSTRUCTIONS``, ``CAPABILITIES`` (tracker ids) and ``TOOLS``.
They use the standard library only, so installing Dex adds no dependency, and they are imported only when served.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

from dex_trove.mcp.common import Context, ToolError

__all__ = ["SERVERS", "Context", "Server", "ToolError", "build", "catalog", "load"]
from dex_trove.mcp.server import Server

SERVERS: dict[str, str] = {
    "jenkins": "dex_trove.mcp.jenkins",
    "kibana": "dex_trove.mcp.kibana",
    "github": "dex_trove.mcp.github_pr",
    "sas": "dex_trove.mcp.sas",
    "onboarding": "dex_trove.mcp.onboarding",
    "browser": "dex_trove.mcp.browser",
    "analytics": "dex_trove.mcp.analytics",
}


def load(name: str) -> ModuleType:
    if name not in SERVERS:
        raise ToolError(f"no MCP server {name!r}; available: {', '.join(sorted(SERVERS))}")
    return importlib.import_module(SERVERS[name])


def build(
    name: str,
    root: Path,
    *,
    allow_actions: bool = False,
    evidence: Path | None = None,
) -> Server:
    module = load(name)
    ctx = Context(root=root, server=name, allow_actions=allow_actions, evidence_dir=evidence)
    return Server(name=name, instructions=module.INSTRUCTIONS, tools=list(module.TOOLS), ctx=ctx)


def catalog() -> list[dict[str, object]]:
    rows = []
    for name in sorted(SERVERS):
        module = load(name)
        rows.append(
            {
                "name": name,
                "title": module.TITLE,
                "tools": [t.name for t in module.TOOLS],
                "actions": [t.name for t in module.TOOLS if t.action],
                "capabilities": list(module.CAPABILITIES),
            }
        )
    return rows
