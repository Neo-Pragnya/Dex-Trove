"""Analytics server: consent first, no prompt text, observed vs estimated vs unknown, opt-out deletes everything."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp_fakes import serve

from dex_trove.mcp import analytics
from dex_trove.mcp.common import Context, ToolError
from dex_trove.mcp.server import Server

DAYS = [
    {
        "date": "2026-11-01",
        "total_active_users": 12,
        "total_engaged_users": 9,
        "copilot_ide_code_completions": {
            "editors": [
                {
                    "name": "vscode",
                    "models": [
                        {
                            "name": "default",
                            "languages": [
                                {
                                    "name": "python",
                                    "total_code_suggestions": 400,
                                    "total_code_acceptances": 60,
                                    "total_code_lines_suggested": 900,
                                    "total_code_lines_accepted": 120,
                                    "total_engaged_users": 6,
                                },
                                {
                                    "name": "typescript",
                                    "total_code_suggestions": 200,
                                    "total_code_acceptances": 90,
                                    "total_engaged_users": 4,
                                },
                            ],
                        }
                    ],
                }
            ]
        },
        "copilot_ide_chat": {
            "editors": [
                {
                    "name": "vscode",
                    "models": [{"name": "default", "total_chats": 30, "total_chat_insertion_events": 5}],
                }
            ]
        },
    }
]
SECRET = "PLEASE-NEVER-COPY-THIS-PROMPT"


def sessions(folder: Path) -> None:
    folder.mkdir()
    lines = [
        {
            "type": "user",
            "sessionId": "s1",
            "timestamp": "2026-11-02T10:00:00Z",
            "message": {"role": "user", "content": SECRET},
        },
        {
            "type": "assistant",
            "sessionId": "s1",
            "timestamp": "2026-11-02T10:00:05Z",
            "message": {
                "usage": {
                    "input_tokens": 1000,
                    "output_tokens": 200,
                    "cache_read_input_tokens": 500,
                    "cache_creation_input_tokens": 3000,
                },
                "content": [
                    {"type": "text", "text": SECRET},
                    {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "a.py"}},
                ],
            },
        },
        {
            "type": "user",
            "sessionId": "s1",
            "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "x" * 4000}]},
        },
        {
            "type": "assistant",
            "sessionId": "s1",
            "message": {
                "usage": {"input_tokens": 10, "output_tokens": 50},
                "content": [{"type": "tool_use", "id": "t2", "name": "Grep"}],
            },
        },
    ]
    (folder / "s1.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n{broken\n")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "metrics.json").write_text(json.dumps(DAYS))
    (tmp_path / "eval.json").write_text(
        json.dumps({"recall": 0.833, "tokens": 5353, "baseline_tokens": 3450000, "saving": 0.998})
    )
    sessions(tmp_path / "logs")
    return tmp_path


def make(root: Path, env: dict[str, str] | None = None) -> Server:
    return Server(
        "analytics",
        analytics.INSTRUCTIONS,
        list(analytics.TOOLS),
        Context(root=root, server="analytics", env=env or {}),
    )


def consent(server: Server, root: Path) -> None:
    server.call(
        "analytics_consent",
        {
            "sources": ["copilot-export", "claude-code-sessions", "context-eval"],
            "exports": ["metrics.json"],
            "sessions_dir": str(root / "logs"),
            "context_eval": "eval.json",
        },
    )


def test_nothing_without_consent(root: Path) -> None:
    server = make(root)
    for tool in ("analytics_sources", "analytics_normalize", "analytics_estimate"):
        with pytest.raises(ToolError, match="no consent"):
            server.call(tool, {})
    with pytest.raises(ToolError, match="copying prompts isn't supported"):
        server.call(
            "analytics_consent",
            {"sources": ["context-eval"], "context_eval": "eval.json", "include_prompts": True},
        )
    with pytest.raises(ToolError, match="sources must be"):
        server.call("analytics_consent", {"sources": ["keylogger"]})


def test_sources_say_what_is_unknown(root: Path) -> None:
    server = make(root)
    consent(server, root)
    out = server.call("analytics_sources", {})
    assert all(s["reachable"] for s in out["sources"])
    assert "copilot tokens" in out["unknown"]


def test_normalize_keeps_counts_not_prompts(root: Path) -> None:
    server = make(root)
    consent(server, root)
    out = server.call("analytics_normalize", {})
    assert out["prompts_copied"] is False and out["sessions"] == 1
    stored = (root / ".dex/mcp/analytics/usage.json").read_text()
    assert SECRET not in stored and "a.py" not in stored
    usage = json.loads(stored)
    s = usage["sessions"][0]
    assert (s["input_tokens"], s["output_tokens"], s["cache_read_tokens"], s["cache_write_tokens"]) == (
        1010,
        250,
        500,
        3000,
    )
    assert s["tools"] == {"Grep": 1, "Read": 1} and s["turns"] == 2
    accepted = [r for r in usage["copilot"] if r["metric"] == "code_acceptances"]
    assert {r["language"]: r["value"] for r in accepted} == {"python": 60, "typescript": 90}
    assert all(r["kind"] == "observed" for r in usage["copilot"])


def test_estimate_and_report_label_everything(root: Path) -> None:
    server = make(root)
    consent(server, root)
    server.call("analytics_normalize", {})
    est = server.call("analytics_estimate", {})["estimate"]
    assert est["kind"] == "estimated" and est["file_read_tokens"] == 1000 and est["tokens_saved"] == 998
    out = server.call("analytics_report", {})
    page = (root / out["artifacts"][0]["path"]).read_text()
    assert "observed" in page and "estimated" in page and "publish Copilot token counts per user" in page
    assert "<script" not in page and SECRET not in page
    assert any("python are accepted 15%" in r for r in out["recommendations"])
    assert any("tool calls read files" in r for r in out["recommendations"])


def test_opt_out_deletes_local_analytics(root: Path) -> None:
    server = make(root)
    consent(server, root)
    server.call("analytics_normalize", {})
    server.call("analytics_report", {})
    out = server.call("analytics_opt_out", {})
    assert set(out["removed"]) == {".dex/mcp/analytics", "dex-evidence/analytics"}
    assert not (root / ".dex/mcp/analytics").exists() and not (root / "dex-evidence/analytics").exists()
    assert (root / "logs/s1.jsonl").exists()  # the user's own logs are never touched
    with pytest.raises(ToolError, match="no consent"):
        server.call("analytics_normalize", {})


def test_fetch_from_the_metrics_api(root: Path) -> None:
    with serve() as fake:
        fake.json("GET", "/orgs/acme/copilot/metrics", DAYS)
        server = make(root, {"GH_TOKEN": "t", "GITHUB_API_URL": fake.base})
        server.call("analytics_consent", {"sources": ["copilot-api"], "org": "acme"})
        assert server.call("analytics_fetch", {})["days"] == 1
        assert server.call("analytics_normalize", {})["copilot_rows"] > 0
        fake.json("GET", "/orgs/acme/copilot/metrics", {"message": "forbidden"}, status=403)
        with pytest.raises(ToolError, match="403 forbidden"):
            server.call("analytics_fetch", {})
