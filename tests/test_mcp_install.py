"""Installing a *-mcp-kit plugin registers its MCP server only with --allow-exec, pinned, never overwriting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dex_trove import __version__, install


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def by_kind(done: list[install.Installed], kind: str) -> install.Installed:
    return next(d for d in done if d.kind == kind)


def test_server_needs_allow_exec(project: Path) -> None:
    done = install.install(["neo-pragnya-mcp/sas-mcp-kit"], target="claude", scope="project")
    assert by_kind(done, "skill").dest == project / ".claude/skills/sas-to-python"
    mcp = by_kind(done, "mcp")
    assert (
        mcp.dest is None
        and "--allow-exec" in mcp.skipped
        and "dex mcp config sas --client claude-code" in mcp.skipped
    )
    assert not (project / ".mcp.json").exists()


def test_claude_project_registration_is_pinned_and_kept(project: Path) -> None:
    (project / ".mcp.json").write_text(json.dumps({"mcpServers": {"mine": {"command": "my-server"}}}))
    done = install.install(["neo-pragnya-mcp/sas-mcp-kit"], target="claude", scope="project", allow_exec=True)
    assert by_kind(done, "mcp").dest == project / ".mcp.json"
    servers = json.loads((project / ".mcp.json").read_text())["mcpServers"]
    assert servers["mine"] == {"command": "my-server"}
    assert servers["dex-sas"]["args"][:2] == ["--from", f"dex-trove=={__version__}"]
    servers["dex-sas"]["args"].append("--allow-actions")  # the user's own edit
    (project / ".mcp.json").write_text(json.dumps({"mcpServers": servers}))
    again = install.install(
        ["neo-pragnya-mcp/sas-mcp-kit"], target="claude", scope="project", allow_exec=True
    )
    assert by_kind(again, "mcp").skipped == "already registered"
    assert (
        json.loads((project / ".mcp.json").read_text())["mcpServers"]["dex-sas"]["args"][-1]
        == "--allow-actions"
    )


def test_copilot_gets_vscode_config(project: Path) -> None:
    install.install(["neo-pragnya-mcp/jenkins-mcp-kit"], target="copilot", allow_exec=True)
    server = json.loads((project / ".vscode/mcp.json").read_text())["servers"]["dex-jenkins"]
    assert server["type"] == "stdio" and server["command"] == "uvx" and "jenkins" in server["args"]
    assert (project / ".github/agents/jenkins-build-steward.agent.md").is_file()


def test_user_scope_and_bad_configs(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: project / "home"))
    done = install.install(["neo-pragnya-mcp/sas-mcp-kit"], target="claude", scope="user", allow_exec=True)
    assert "doesn't edit ~/.claude.json" in by_kind(done, "mcp").skipped
    (project / ".mcp.json").write_text("{not json")
    with pytest.raises(install.InstallError, match="left alone"):
        install.install(["neo-pragnya-mcp/sas-mcp-kit"], target="claude", scope="project", allow_exec=True)
    assert (project / ".mcp.json").read_text() == "{not json"
