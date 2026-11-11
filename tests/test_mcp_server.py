"""The MCP protocol layer: handshake, tool listing, argument checks, errors, and stdio framing."""

from __future__ import annotations

import io
import json
import secrets
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dex_trove.cli import app
from dex_trove.mcp import SERVERS, build, catalog
from dex_trove.mcp.common import (
    Context,
    ToolError,
    approval_for,
    redact,
    redact_obj,
    require_approval,
    stable_digest,
)


def rpc(server, method, params=None, mid=1):  # type: ignore[no-untyped-def]
    return server.handle({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})


def test_initialize_and_list(tmp_path: Path) -> None:
    server = build("jenkins", tmp_path)
    init = rpc(
        server,
        "initialize",
        {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t"}},
    )
    assert init["result"]["protocolVersion"] == "2025-03-26"
    assert init["result"]["serverInfo"]["name"] == "dex-jenkins"
    assert "tools" in init["result"]["capabilities"]
    assert (
        rpc(server, "initialize", {"protocolVersion": "1999-01-01"})["result"]["protocolVersion"]
        == "2025-06-18"
    )
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    tools = {t["name"]: t for t in rpc(server, "tools/list")["result"]["tools"]}
    assert tools["jenkins_trigger"]["annotations"]["destructiveHint"] is True
    assert tools["jenkins_preview"]["annotations"]["readOnlyHint"] is True
    assert tools["jenkins_trigger"]["inputSchema"]["additionalProperties"] is False


def test_errors_are_answers_not_crashes(tmp_path: Path) -> None:
    server = build("jenkins", tmp_path)
    assert rpc(server, "nope")["error"]["code"] == -32601
    assert server.handle({"id": 1, "method": "ping"})["error"]["code"] == -32600
    bad = rpc(server, "tools/call", {"name": "jenkins_preview", "arguments": {"job": "x", "surprise": 1}})[
        "result"
    ]
    assert bad["isError"] and "unknown argument" in bad["content"][0]["text"]
    missing = rpc(server, "tools/call", {"name": "jenkins_preview", "arguments": {}})["result"]
    assert missing["isError"] and "missing required" in missing["content"][0]["text"]
    typed = rpc(server, "tools/call", {"name": "jenkins_check", "arguments": {"job": "x", "pr": "5"}})[
        "result"
    ]
    assert typed["isError"] and "pr must be integer" in typed["content"][0]["text"]
    noconf = rpc(server, "tools/call", {"name": "jenkins_jobs", "arguments": {}})["result"]
    assert noconf["isError"] and ".dex/jenkins.json" in noconf["content"][0]["text"]


def test_stdio_framing(tmp_path: Path) -> None:
    server = build("jenkins", tmp_path)
    lines = "\n".join(
        [
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
            "{not json",
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            "",
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        ]
    )
    out = io.StringIO()
    server.serve(io.StringIO(lines + "\n"), out)
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [r.get("id") for r in replies] == [1, None, 2]
    assert replies[1]["error"]["code"] == -32700


def test_paths_stay_inside_root(tmp_path: Path) -> None:
    ctx = Context(root=tmp_path, server="t")
    (tmp_path / "a.txt").write_text("x")
    assert ctx.path("a.txt") == (tmp_path / "a.txt").resolve()
    for bad in ("../etc/passwd", "/etc/passwd", ""):
        with pytest.raises(ToolError):
            ctx.path(bad)
    (tmp_path / "link").symlink_to("/etc")
    with pytest.raises(ToolError, match="outside"):
        ctx.path("link/hosts")


def test_approval_needs_actions_and_the_exact_plan(tmp_path: Path) -> None:
    plan = {"action": "x", "n": 1}
    with pytest.raises(ToolError, match="actions are off"):
        require_approval(Context(root=tmp_path, server="t"), plan, approval_for(plan), action="x")
    ctx = Context(root=tmp_path, server="t", allow_actions=True)
    with pytest.raises(ToolError, match="doesn't match"):
        require_approval(ctx, plan, approval_for({**plan, "n": 2}), action="x")
    require_approval(ctx, plan, approval_for(plan), action="x")
    audit = [json.loads(line) for line in (tmp_path / ".dex/mcp/audit.jsonl").read_text().splitlines()]
    assert [a["event"] for a in audit] == ["refused", "refused", "approved"]


def test_digest_ignores_timestamps() -> None:
    assert stable_digest({"a": 1, "generated_at": "x"}) == stable_digest({"generated_at": "y", "a": 1})
    assert stable_digest({"a": 1}) != stable_digest({"a": 2})


def test_redaction() -> None:
    # Fake credentials made at run time, so nothing secret-shaped is committed.
    pat, bearer, query = "ghp_" + secrets.token_hex(16), secrets.token_hex(10), secrets.token_hex(6)
    text = f"Authorization: Bearer {bearer} url=https://u:p@host/x?token={query}&ok=1 {pat}"
    out = redact(text)
    assert query not in out and pat not in out and "u:p@" not in out and bearer not in out
    assert "ok=1" in out
    assert redact_obj({"Cookie": "sid=1", "name": "fine"}) == {"Cookie": "[REDACTED]", "name": "fine"}


def test_catalog_and_cli(tmp_path: Path) -> None:
    rows = {r["name"]: r for r in catalog()}
    assert set(rows) == set(SERVERS)
    runner = CliRunner()
    listed = runner.invoke(app, ["mcp", "list", "--json"])
    assert listed.exit_code == 0 and json.loads(listed.output)
    for client in ("claude-code", "vscode", "codex", "json"):
        res = runner.invoke(app, ["mcp", "config", "jenkins", "--client", client])
        assert res.exit_code == 0 and "dex-trove==" in res.output
    res = runner.invoke(app, ["mcp", "call", "jenkins", "jenkins_jobs", "--root", str(tmp_path)])
    assert res.exit_code == 2 and ".dex/jenkins.json" in res.output
    assert runner.invoke(app, ["mcp", "serve", "nope"]).exit_code == 2


def test_servers_add_no_dependencies() -> None:
    """Every server module imports only the standard library and Dex."""
    import ast
    import sys

    folder = Path(__file__).parents[1] / "src/dex_trove/mcp"
    for path in folder.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom) and node.level == 0
                else []
            )
            for name in names:
                top = name.split(".")[0]
                assert top in sys.stdlib_module_names or top in {"dex_trove", "typer", "__future__"}, (
                    path.name,
                    name,
                )
