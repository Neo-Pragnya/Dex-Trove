"""GitHub PR server: a real git repository with a local bare remote, and a fake gh that records its calls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from dex_trove.mcp import github_pr
from dex_trove.mcp.common import Context, ToolError
from dex_trove.mcp.server import Server

FAKE_GH = r"""
import json, os, sys
state = os.environ["FAKE_GH_STATE"]
data = json.load(open(state)) if os.path.exists(state) else {"calls": [], "prs": {}}
args = sys.argv[1:]
data["calls"].append(args)
code, out = 0, ""
if args[:2] == ["pr", "view"]:
    pr = data["prs"].get(args[2])
    code, out = (0, json.dumps(pr)) if pr else (1, "")
elif args[:2] == ["pr", "create"]:
    if os.environ.get("FAKE_GH_FAIL") == "create":
        code = 1
    else:
        head = args[args.index("--head") + 1]
        data["prs"][head] = {"number": 7, "url": "https://github.com/acme/app/pull/7", "state": "OPEN"}
        data["body"] = open(args[args.index("--body-file") + 1]).read()
        out = "https://github.com/acme/app/pull/7"
elif args[:2] == ["pr", "comment"]:
    data["comment"] = open(args[args.index("--body-file") + 1]).read()
json.dump(data, open(state, "w"))
print(out)
if code:
    print("gh: something went wrong", file=sys.stderr)
sys.exit(code)
"""


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    work = tmp_path / "work"
    work.mkdir()
    git(work, "init", "-q", "-b", "main")
    git(work, "config", "user.email", "t@example.com")
    git(work, "config", "user.name", "T")
    (work / "a.txt").write_text("a\n")
    git(work, "add", ".")
    git(work, "commit", "-qm", "first")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "push", "-q", "origin", "main")
    git(work, "checkout", "-qb", "feat/x")
    (work / "a.txt").write_text("b\n")
    git(work, "commit", "-qam", "change a")
    (work / "PR.md").write_text("# Change a\n\nWhy and what.\n")
    (work / "report.json").write_text('{"ok": true}\n')
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(f"#!{sys.executable}\n{FAKE_GH}")
    gh.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_GH_STATE": str(tmp_path / "gh.json"),
    }
    return work, env


def make(root: Path, env: dict[str, str], *, allow: bool = False) -> Server:
    ctx = Context(root=root, server="github", allow_actions=allow, env=env)
    return Server("github", github_pr.INSTRUCTIONS, list(github_pr.TOOLS), ctx)


ARGS = {"body": "PR.md", "evidence": ["report.json"]}


def gh_state(env: dict[str, str]) -> dict:  # type: ignore[type-arg]
    path = Path(env["FAKE_GH_STATE"])
    return json.loads(path.read_text()) if path.exists() else {"calls": []}


def test_preview_is_static_and_creates_nothing(repo: tuple[Path, dict[str, str]]) -> None:
    work, env = repo
    out = make(work, env).call("github_pr_preview", ARGS)
    assert out["status"] == "needs-approval" and out["plan"]["title"] == "Change a"
    assert [c["subject"] for c in out["plan"]["commits"]] == ["change a"]
    assert out["plan"]["evidence"][0]["path"] == "report.json"
    page = (work / "dex-evidence/github/pr-preview.html").read_text()
    assert "<form" not in page and "<script" not in page and "default-src 'none'" in page
    assert gh_state(env)["calls"] == []
    assert git(work, "ls-remote", "origin", "feat/x") == ""


def test_create_needs_approval_then_runs_once(repo: tuple[Path, dict[str, str]]) -> None:
    work, env = repo
    preview = make(work, env).call("github_pr_preview", ARGS)
    with pytest.raises(ToolError, match="actions are off"):
        make(work, env).call("github_pr_create", {**ARGS, "approval": preview["approval"]})
    with pytest.raises(ToolError, match="doesn't match"):
        make(work, env, allow=True).call(
            "github_pr_create", {**ARGS, "draft": False, "approval": preview["approval"]}
        )
    out = make(work, env, allow=True).call("github_pr_create", {**ARGS, "approval": preview["approval"]})
    assert out["status"] == "created" and out["url"].endswith("/pull/7")
    assert git(work, "ls-remote", "origin", "feat/x").split()[0] == git(work, "rev-parse", "HEAD")
    state = gh_state(env)
    create = next(c for c in state["calls"] if c[:2] == ["pr", "create"])
    assert "--draft" in create and create[create.index("--base") + 1] == "main"
    assert "## Evidence" in state["body"] and preview["plan"]["evidence"][0]["sha256"] in state["body"]
    again = make(work, env, allow=True).call("github_pr_create", {**ARGS, "approval": preview["approval"]})
    assert again["status"] == "already-open"
    assert sum(1 for c in gh_state(env)["calls"] if c[:2] == ["pr", "create"]) == 1


def test_blocked_states(repo: tuple[Path, dict[str, str]]) -> None:
    work, env = repo
    (work / "a.txt").write_text("dirty\n")
    out = make(work, env).call("github_pr_preview", ARGS)
    assert out["status"] == "blocked" and "uncommitted" in out["blocked_by"][0] and out["approval"] is None
    git(work, "checkout", "-q", "a.txt")
    git(work, "checkout", "-q", "main")
    out = make(work, env).call("github_pr_preview", ARGS)
    assert any("is the base" in p for p in out["blocked_by"])
    with pytest.raises(ToolError, match="valid branch"):
        make(work, env).call("github_pr_preview", {**ARGS, "base": "--upload-pack=x"})


def test_failures_are_reported_per_step(repo: tuple[Path, dict[str, str]]) -> None:
    work, env = repo
    preview = make(work, env).call("github_pr_preview", ARGS)
    out = make(work, {**env, "FAKE_GH_FAIL": "create"}, allow=True).call(
        "github_pr_create", {**ARGS, "approval": preview["approval"]}
    )
    assert out["status"] == "failed" and [s["ok"] for s in out["steps"]] == [True, False]
    assert "pushed feat/x" in out["warnings"][0]
    git(work, "remote", "set-url", "origin", str(work.parent / "nowhere.git"))
    preview = make(work, env).call("github_pr_preview", ARGS)
    out = make(work, env, allow=True).call("github_pr_create", {**ARGS, "approval": preview["approval"]})
    assert out["status"] == "failed" and out["steps"][0]["step"] == "push" and not out["steps"][0]["ok"]


def test_attach_refuses_changed_evidence(repo: tuple[Path, dict[str, str]]) -> None:
    work, env = repo
    preview = make(work, env).call("github_pr_preview", ARGS)
    recorded = {e["path"]: e["sha256"] for e in preview["plan"]["evidence"]}
    args = {"pr": 7, "evidence": ["report.json"], "expected": recorded}
    attach = make(work, env).call("github_pr_attach_preview", args)
    assert recorded["report.json"] in attach["comment"]
    out = make(work, env, allow=True).call("github_pr_attach", {**args, "approval": attach["approval"]})
    assert out["status"] == "attached" and recorded["report.json"] in gh_state(env)["comment"]
    (work / "report.json").write_text('{"ok": false}\n')
    with pytest.raises(ToolError, match="changed since"):
        make(work, env).call("github_pr_attach_preview", args)
