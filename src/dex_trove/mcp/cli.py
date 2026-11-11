"""``dex mcp``: list, configure, serve and call the local MCP servers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from dex_trove import __version__

mcp_app = typer.Typer(
    help="Local MCP servers for systems Dex can't reach by itself (Jenkins, Kibana, GitHub...): stdio, offline-first, "
    "and dry-run unless started with --allow-actions.",
    no_args_is_help=True,
)
CLIENTS = ("claude-code", "vscode", "codex", "json")
RootOpt = Annotated[
    Path, typer.Option("--root", help="Project the server works in (it reads and writes only here)")
]
AllowOpt = Annotated[
    bool,
    typer.Option(
        "--allow-actions", help="Let approved tools change external systems. Off by default: preview only"
    ),
]
EvidenceOpt = Annotated[
    Path | None, typer.Option("--evidence", help="Evidence folder (default <root>/dex-evidence)")
]


def _fail(exc: Exception) -> typer.Exit:
    typer.echo(f"error: {exc}", err=True)
    return typer.Exit(2)


@mcp_app.command("list")
def list_servers(as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """The servers, their tools, which tools act on external systems, and the tracker tasks they cover."""
    from dex_trove.mcp import catalog

    rows = catalog()
    if as_json:
        typer.echo(json.dumps(rows, indent=1))
        return
    for row in rows:
        acts = f"  (acts: {', '.join(row['actions'])})" if row["actions"] else ""  # type: ignore[arg-type]
        typer.echo(f"{row['name']:<12} {row['title']}{acts}")
        typer.echo(f"{'':<12} tools: {', '.join(row['tools'])}")  # type: ignore[arg-type]


@mcp_app.command("serve")
def serve(
    name: str, root: RootOpt = Path("."), allow_actions: AllowOpt = False, evidence: EvidenceOpt = None
) -> None:
    """Run a server on stdin/stdout (what an MCP client starts)."""
    from dex_trove.mcp import ToolError, build

    try:
        server = build(name, root, allow_actions=allow_actions, evidence=evidence)
    except ToolError as exc:
        raise _fail(exc) from exc
    server.serve(sys.stdin, sys.stdout)


@mcp_app.command("call")
def call(
    name: str,
    tool: str,
    args: Annotated[str, typer.Option("--args", help="Tool arguments as a JSON object")] = "{}",
    root: RootOpt = Path("."),
    allow_actions: AllowOpt = False,
    evidence: EvidenceOpt = None,
) -> None:
    """Call one tool once from the shell and print its JSON result. Same rules as over MCP."""
    from dex_trove.mcp import ToolError, build

    try:
        parsed = json.loads(args)
    except ValueError as exc:
        raise _fail(ValueError(f"--args isn't JSON: {exc}")) from exc
    try:
        out = build(name, root, allow_actions=allow_actions, evidence=evidence).call(tool, parsed)
    except ToolError as exc:
        raise _fail(exc) from exc
    typer.echo(json.dumps(out, indent=1, ensure_ascii=False))


@mcp_app.command("config")
def config(
    name: str,
    client: Annotated[str, typer.Option("--client", help=f"One of {', '.join(CLIENTS)}")] = "json",
    root: Annotated[str, typer.Option("--root", help="Project path the client should pass")] = ".",
    allow_actions: AllowOpt = False,
) -> None:
    """How to register a server with an MCP client, pinned to this Dex version. Prints; changes nothing."""
    from dex_trove.mcp import ToolError, load

    try:
        load(name)
    except ToolError as exc:
        raise _fail(exc) from exc
    if client not in CLIENTS:
        raise _fail(ValueError(f"--client must be one of {', '.join(CLIENTS)}"))
    args = ["--from", f"dex-trove=={__version__}", "dex", "mcp", "serve", name, "--root", root]
    if allow_actions:
        args.append("--allow-actions")
    key = f"dex-{name}"
    if client == "claude-code":
        typer.echo(f"claude mcp add {key} -- uvx {' '.join(args)}")
    elif client == "vscode":
        typer.echo(
            json.dumps({"servers": {key: {"type": "stdio", "command": "uvx", "args": args}}}, indent=2)
        )
    elif client == "codex":
        quoted = ", ".join(json.dumps(a) for a in args)
        typer.echo(f'[mcp_servers.{key.replace("-", "_")}]\ncommand = "uvx"\nargs = [{quoted}]')
    else:
        typer.echo(json.dumps({"mcpServers": {key: {"command": "uvx", "args": args}}}, indent=2))
